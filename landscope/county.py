"""Official county RCN GML: explicit links, units and complete sale scope."""
import io
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal
from .sources import fetch, archive, xml, normalize_rcn
from .geometry import local, gml_geometry
from .domain import ContractError, number, full_share

CATALOG = 'https://api.dane.gov.pl/1.4/datasets/29243/resources'
SOURCE = 'https://dane.gov.pl/pl/dataset/29243,rejestr-cen-nieruchomosci-rcn-powiatu-gorzowskiego'
GML_ID = '{http://www.opengis.net/gml/3.2}id'
HREF = '{http://www.w3.org/1999/xlink}href'
CODES = json.loads((Path(__file__).parent/'rcn_codes.json').read_text(encoding='utf-8'))


def text(node, name):
    return next(((e.text or '').strip() or None for e in node.iter() if local(e.tag)==name), None)


def child(node, name):
    return next(((e.text or '').strip() or None for e in node if local(e.tag)==name), None)


def refs(node, name):
    return [e.get(HREF,'').lstrip('#') for e in node if local(e.tag)==name]


def address_parts(node, name):
    result = []
    for wrapper in (e for e in node if local(e.tag)==name):
        for address in wrapper:
            parts = {'city':child(address,'miejscowosc'),'street':child(address,'ulica'),'number':child(address,'numerPorzadkowy')}
            if any(parts.values()):
                result.append(parts)
    return result


def addresses(node, name):
    return [' '.join(filter(None,[p['city'],p['street'],p['number']])) for p in address_parts(node,name)]


def building(node):
    return {'id':child(node,'idBudynku'),'kind':code_child(node,'rodzajBudynku','RCN_RodzajBudynkuType'),
            'usable_area':area(node,'powierzchniaUzytkowaBudynku'),'price':child(node,'cenaBudynkuBrutto'),
            'vat':child(node,'kwotaPodatkuVAT'),'info':child(node,'dodatkoweInformacje'),
            'addresses':addresses(node,'adresBudynku')}


def premises(node):
    return {'id':child(node,'idLokalu'),'function':code_child(node,'funkcjaLokalu','RCN_FunkcjaLokaluType'),
            'rooms':child(node,'liczbaIzb'),'floor':child(node,'nrKondygnacji'),
            'usable_area':area(node,'powUzytkowaLokalu'),'auxiliary_area':area(node,'powUzytkowaPomieszczenPrzynal'),
            'price':child(node,'cenaLokaluBrutto'),'vat':child(node,'kwotaPodatkuVAT'),
            'info':child(node,'dodatkoweInformacje'),'addresses':addresses(node,'adresBudynkuZLokalem')}


def area(node, name):
    el = next((e for e in node if local(e.tag)==name),None)
    if el is None or not el.text:
        return None
    unit = el.get('uom')
    if unit not in {'ha','m2','m²'}:
        raise ContractError('Nieznana jednostka powierzchni GML: '+str(unit))
    return str(number(el.text) * (Decimal(10000) if unit=='ha' else Decimal(1)))


def decode(value, name, dictionary):
    if value is None:
        return None
    if value not in CODES[dictionary]:
        raise ContractError('Nieznany kod '+name+': '+value)
    return CODES[dictionary][value]


def code(node, name, dictionary):
    return decode(text(node,name),name,dictionary)


def code_child(node, name, dictionary):
    return decode(child(node,name),name,dictionary)


def unzip(content):
    if not content.startswith(b'PK'):
        return content
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        members=[i for i in z.infolist() if i.filename.lower().endswith('.gml')]
        if len(members)!=1 or members[0].file_size>500_000_000:
            raise ContractError('Archiwum musi zawierać jeden GML do 500 MB')
        return z.read(members[0])


def latest_resource():
    response=fetch(CATALOG)
    archive(response,'rcn_county')
    body=response.json()
    resources=body.get('data',[])
    total=(body.get('meta') or {}).get('count')
    if isinstance(total,int) and total>len(resources):
        raise ContractError('Katalog zwrócił niepełną listę zasobów')
    candidates=[r['attributes'] for r in resources if r['attributes'].get('format') in {'zip','gml'}]
    if not candidates:
        raise ContractError('Brak pliku GML/ZIP powiatu')
    # Catalog order is NOT chronological.
    return max(candidates,key=lambda r:(r.get('data_date') or '',r.get('modified') or ''))


def download_county():
    metadata=latest_resource()
    response=fetch(metadata['link'])
    path=archive(response,'rcn_county')
    return response.content,metadata,path


def county_records(content, snapshot=None):
    root=xml(unzip(content))
    if local(root.tag)!='FeatureCollection':
        raise ContractError('Brak kolekcji GML RCN')
    nodes={}
    counts=Counter()
    for member in root:
        for node in member:
            if not local(node.tag).startswith('RCN_'):
                continue
            if not node.tag.startswith('{https://geoportal.gov.pl/schemas/rcn/1.5}'):
                raise ContractError('Nieobsługiwana wersja GML RCN; oczekiwano 1.5')
            identifier=node.get(GML_ID)
            if not identifier or identifier in nodes:
                raise ContractError('Brak lub duplikat gml:id')
            nodes[identifier]=node
            counts[local(node.tag)]+=1
    def linked(node,name,kind):
        result=[]
        for ref in refs(node,name):
            if ref not in nodes or local(nodes[ref].tag)!=kind:
                raise ContractError('Zerwana relacja '+name+': '+ref)
            result.append(nodes[ref])
        return result
    result=[]
    for tx in nodes.values():
        if local(tx.tag)!='RCN_Transakcja':
            continue
        docs=linked(tx,'podstawaPrawna','RCN_Dokument')
        properties=linked(tx,'nieruchomosc','RCN_Nieruchomosc')
        if len(docs)!=1 or not properties:
            raise ContractError('Transakcja bez dokumentu lub nieruchomości')
        all_parcels=[p for prop in properties for p in linked(prop,'dzialka','RCN_Dzialka')]
        all_ids=[text(p,'idDzialki') for p in all_parcels]
        areas=[number(area(p,'polePowierzchniEwidencyjnej')) for p in all_parcels]
        # A land-only complete transaction may have a scoped total unit price.
        # A premises/building sale or repeated parcel through different rights may not.
        complete_land=bool(all_parcels) and len(set(all_ids))==len(all_ids) and all(
            text(p,'rodzajNieruchomosci')=='1' and not refs(p,'budynek') and not refs(p,'lokal') for p in properties)
        valid_area=all(a is not None and a>0 for a in areas)
        tx_area=str(sum(areas)) if valid_area and areas else None
        all_share=all(full_share(text(p,'udzialWPrawieDoNieruchomosci')) for p in properties)
        transaction_details={
            'designation':child(tx,'oznaczenieTransakcji'),'vat':child(tx,'kwotaPodatkuVAT'),
            'seller_type':code_child(tx,'stronaSprzedajaca','RCN_StronaSprzedajacaKupujacaType'),
            'buyer_type':code_child(tx,'stronaKupujaca','RCN_StronaSprzedajacaKupujacaType'),
            'document':child(docs[0],'oznaczenieDokumentu'),'parcel_ids':all_ids,
        }
        for prop in properties:
            parcels=linked(prop,'dzialka','RCN_Dzialka')
            # Validate all relationship types, including objects excluded from land statistics.
            buildings=[building(b) for b in linked(prop,'budynek','RCN_Budynek')]
            units=[premises(u) for u in linked(prop,'lokal','RCN_Lokal')]
            property_details={'description':child(prop,'opis'),'vat':child(prop,'kwotaPodatkuVAT'),
                              'parcel_ids':[text(p,'idDzialki') for p in parcels],'buildings':buildings,'premises':units}
            for parcel in parcels:
                parcel_addresses=addresses(parcel,'adresDzialki')
                geometry,error=None,None
                try:
                    geometry=gml_geometry(parcel)
                except ContractError as exc:
                    error=str(exc)
                fields={
                    'tran_przestrzen_nazw':text(tx,'przestrzenNazw'),
                    'tran_lokalny_id_iip':text(tx,'lokalnyId'),
                    'tran_wersja_id':text(tx,'wersjaId'),
                    'tran_cena_brutto':text(tx,'cenaTransakcjiBrutto'),
                    'tran_rodzaj_trans':code(tx,'rodzajTransakcji','RCN_RodzajTransakcjiType'),
                    'tran_rodzaj_rynku':code(tx,'rodzajRynku','RCN_RodzajRynkuType'),
                    'dok_data':text(docs[0],'dataSporzadzeniaDokumentu'),
                    'nier_rodzaj':code(prop,'rodzajNieruchomosci','RCN_RodzajNieruchomosciType'),
                    'nier_prawo':code(prop,'rodzajPrawaDoNieruchomosci','RCN_RodzajPrawaType'),
                    'nier_udzial':text(prop,'udzialWPrawieDoNieruchomosci'),
                    'nier_pow_gruntu':area(prop,'polePowierzchniNieruchomosciGruntowej'),
                    'nier_cena_brutto':text(prop,'cenaNieruchomosciBrutto'),
                    'dzi_id_dzialki':text(parcel,'idDzialki'),
                    'dzi_pow_ewid':area(parcel,'polePowierzchniEwidencyjnej'),
                    'dzi_cena_brutto':child(parcel,'cenaDzialkiEwidencyjnejBrutto'),
                    'dzi_sposob_uzyt':code(parcel,'sposobUzytkowania','RCN_SposobUzytkowaniaType'),
                    'dzi_przezn_wmpzp':code(parcel,'przeznaczenieWMPZP','RCN_PrzeznaczenieWMPZPType'),
                    'dzi_adres':'; '.join(parcel_addresses) or None,
                    '_details':{'transaction':transaction_details,'property':property_details,
                                'parcel':{'addresses':parcel_addresses,'address_parts':address_parts(parcel,'adresDzialki'),
                                          'vat':child(parcel,'kwotaPodatkuVAT'),
                                          'info':child(parcel,'dodatkoweInformacje')}},
                    '_source':SOURCE,'_source_snapshot':snapshot,'_area_unit':'m2',
                    '_property_identity':'confirmed','_property_source_id':prop.get(GML_ID),
                    '_property_parcel_count':len(parcels),'_transaction_parcel_count':len(all_parcels),
                    '_transaction_property_count':len(properties),'_transaction_complete_land':complete_land,
                    '_transaction_area':tx_area,'_transaction_full_share':all_share,
                }
                # Stable identity includes links: one parcel can belong to multiple rights.
                fid='county:'+tx.get(GML_ID)+':'+prop.get(GML_ID)+':'+parcel.get(GML_ID)
                result.append({'fields':fields,'feature_id':fid,'geometry':geometry,'geometry_error':error,
                    'raw_xml':{k:ET.tostring(n,encoding='unicode') for k,n in
                               [('transaction',tx),('property',prop),('parcel',parcel),('document',docs[0])]}})
    if not result:
        raise ContractError('Brak rekordów działek w pliku powiatowym')
    return result,dict(counts)


def import_county(county='0801'):
    if county!='0801':
        raise ContractError('Katalog powiatowy skonfigurowany tylko dla 0801')
    from .db import initialize
    from .importer import save_batch
    initialize()
    content,metadata,path=download_county()
    rows,counts=county_records(content,metadata.get('data_date'))
    report=save_batch(rows,county,source_url=SOURCE)
    report.update({'source_objects':counts,'snapshot':metadata.get('data_date'),'archive':path,'download_url':metadata['link']})
    from psycopg.types.json import Jsonb
    from .db import connect
    with connect() as db:
        db.execute("UPDATE import_run SET report=%s WHERE id=%s",(Jsonb(report),report["run_id"]))
    return report
