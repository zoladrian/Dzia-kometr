import argparse
import json
import logging
import random
import sys
from pathlib import Path
from .domain import ContractError
from .sources import Unavailable


def emit(value):
    print(json.dumps(value,ensure_ascii=False,indent=2,default=str))


STATUS = {"confirmed":"źródło","inferred":"wyliczone","unavailable":"brak"}


def print_card(card):
    print(card["title"]+"  ["+card["id"]+"]")
    def block(sections, indent=""):
        for sec in sections:
            print("\n"+indent+"== "+sec["title"]+" ==")
            for r in sec["rows"]:
                print(f"{indent}{r['label']:<46} {r['value']}   ({STATUS[r['status']]}{', '+r['source'] if r.get('source') else ''})")
    block(card["sections"])
    for sale in card["sales"]:
        print("\n### "+sale["title"])
        block(sale["sections"],"  ")


def print_ui_report(report):
    for view in report["views"]:
        print(f"\n[{view['viewport']}] {view['parcel']}: {view['checked']} wartości, błędów {len(view['failures'])}, zrzut {view['screenshot']}")
        for check in view["layout"]:
            print(f"  {'PASS' if check['ok'] else 'FAIL'}  {check['name']}: {check['detail']}")
        for failure in view["failures"][:40]:
            print(f"  FAIL  {failure}")
    print("\nWYNIK:", "PASS" if not report["failures"] else f"FAIL ({report['failures']} błędów)")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "test":
        import pytest
        sys.exit(pytest.main(sys.argv[2:]))
    parser = argparse.ArgumentParser(prog="landscope")
    sub = parser.add_subparsers(dest="command",required=True)
    serve = sub.add_parser("serve"); serve.add_argument("--host",default="127.0.0.1"); serve.add_argument("--port",type=int,default=8000)
    sub.add_parser("init")
    sub.add_parser("counts")
    sub.add_parser("quality")
    sub.add_parser("status")
    diag = sub.add_parser("diagnose"); diag.add_argument("--source",action="append"); diag.add_argument("--parcel")
    imp = sub.add_parser("import-rcn"); imp.add_argument("--county",default="0801"); imp.add_argument("--resume"); imp.add_argument("--page-size",type=int,default=500)
    imp.add_argument('--source',choices=['county','wfs'],default=None)
    file = sub.add_parser("import-file"); file.add_argument("path"); file.add_argument("--county",default="0801")
    search = sub.add_parser("parcel"); search.add_argument("query")
    inspect = sub.add_parser("inspect"); inspect.add_argument("id"); inspect.add_argument("--raw",action="store_true")
    area = sub.add_parser("transactions"); area.add_argument("--bbox",required=True); area.add_argument("--limit",type=int,default=50)
    sample = sub.add_parser("sample"); sample.add_argument("--place",default="Kłodawa"); sample.add_argument("--count",type=int,default=5); sample.add_argument("--seed",type=int,default=8012026)
    addr = sub.add_parser("address"); addr.add_argument("query")
    card = sub.add_parser("card"); card.add_argument("id"); card.add_argument("--json",action="store_true")
    card.add_argument("--transaction",action="store_true",help="ID to identyfikator transakcji")
    fav = sub.add_parser("favorite"); fav.add_argument("id"); fav.add_argument("--label",default=""); fav.add_argument("--remove",action="store_true")
    ui = sub.add_parser("ui-check"); ui.add_argument("--parcel",action="append",required=True)
    ui.add_argument("--url",default="http://127.0.0.1:8000"); ui.add_argument("--out",default="test-results/ui")
    tests = sub.add_parser("test"); tests.add_argument("args",nargs=argparse.REMAINDER)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        from . import db
        if args.command=="serve":
            import uvicorn
            uvicorn.run("landscope.api:app",host=args.host,port=args.port)
        elif args.command=="init":
            db.initialize(); emit({"status":"PASS"})
        elif args.command=="counts":
            emit(db.counts())
        elif args.command=="diagnose":
            from .diagnostics import diagnose
            result=diagnose(args.source,args.parcel); emit(result)
            if any(r["status"]!="PASS" for r in result): sys.exit(1)
        elif args.command=="status":
            path=Path("reports/sources.json")
            emit({"sources":json.loads(path.read_text(encoding="utf-8")) if path.exists() else [],"counts":db.counts()})
        elif args.command=="quality":
            from .repository import quality_report
            emit(quality_report())
        elif args.command=="import-rcn":
            from .importer import import_rcn
            from .county import import_county
            source=args.source or ('county' if args.county=='0801' else 'wfs')
            result=import_county(args.county) if source=='county' else import_rcn(args.county,args.resume,args.page_size)
            emit(result)
            if not result["complete"]: sys.exit(1)
        elif args.command=="import-file":
            from .sources import rcn_page
            from .importer import save_batch
            db.initialize()
            rows,_=rcn_page(Path(args.path).read_bytes())
            # An arbitrary file is never assumed to be the complete county snapshot.
            emit(save_batch(rows,args.county,source_url="local:"+str(Path(args.path).resolve()),complete=False))
        elif args.command=="parcel":
            from .sources import lookup_parcel
            from .repository import save_parcel
            db.initialize()
            found=lookup_parcel(args.query)
            for item in found: save_parcel(item)
            emit(found)
        elif args.command=="inspect":
            from .repository import transaction_detail
            if args.raw:
                with db.connect() as conn:
                    # CLI-only raw evidence; not served through HTTP.
                    emit(conn.execute("SELECT * FROM raw_record WHERE observation_id=%s ORDER BY id",(args.id,)).fetchall())
            else: emit(transaction_detail(args.id))
        elif args.command=="transactions":
            from .api import bbox_value
            from .repository import transactions
            emit(transactions({"bbox":bbox_value(args.bbox)},min(200,max(1,args.limit))))
        elif args.command=="sample":
            from .domain import fold_text, FOLD_FROM, FOLD_TO
            with db.connect() as conn:
                rows=conn.execute("""SELECT DISTINCT o.parcel_id FROM observation o JOIN parcel p ON p.id=o.parcel_id
                  WHERE o.active AND lower(translate(concat_ws(' ',o.address,p.commune,p.region),%s,%s)) LIKE %s
                  ORDER BY o.parcel_id""",(FOLD_FROM,FOLD_TO,"%"+fold_text(args.place)+"%")).fetchall()
            chosen=random.Random(args.seed).sample(rows,min(len(rows),args.count))
            emit({"place":args.place,"seed":args.seed,"population":len(rows),"sample":chosen})
            if not rows: sys.exit(1)
        elif args.command=="address":
            from .repository import parcels_for_address
            db.initialize()
            found=parcels_for_address(args.query)
            emit([{k:v for k,v in item.items() if k!="geometry"} for item in found])
        elif args.command=="card":
            from .repository import parcel_card, transaction_card
            from .domain import parcel_id
            result=transaction_card(args.id) if args.transaction else parcel_card(parcel_id(args.id))
            if result is None:
                emit({"status":"FAIL","reason":"Nie znaleziono"}); sys.exit(1)
            if args.json:
                emit(result)
            else:
                print_card(result)
        elif args.command=="favorite":
            from .repository import set_favorite, parcel_detail
            from .domain import parcel_id
            pid=parcel_id(args.id)
            if not args.remove and parcel_detail(pid) is None:
                emit({"status":"FAIL","reason":"Najpierw wyszukaj działkę (parcel/address)"}); sys.exit(1)
            set_favorite(pid,None if args.remove else args.label)
            emit({"status":"PASS","parcel":pid,"label":None if args.remove else args.label})
        elif args.command=="ui-check":
            from .uicheck import run
            report=run(args.parcel,args.url,args.out)
            print_ui_report(report)
            if report["failures"]: sys.exit(1)
        elif args.command=="test":
            import pytest
            sys.exit(pytest.main(args.args))
    except (Unavailable,ImportError,ContractError) as exc:
        emit({"status":"UNAVAILABLE" if isinstance(exc,(Unavailable,ImportError)) else "FAIL","reason":str(exc)})
        sys.exit(1)
    except Exception as exc:
        logging.exception("Nie udało się wykonać polecenia")
        emit({"status":"FAIL","reason":str(exc)})
        sys.exit(1)
