import argparse,json
from pathlib import Path
from .database import ROOT,connect,audit_database

def main():
    p=argparse.ArgumentParser(description='Corporate financial distress database')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('audit');a.add_argument('--database',default=str(ROOT/'data/derived/distress.sqlite'))
    a=sub.add_parser('features');a.add_argument('--database',default=str(ROOT/'data/derived/distress.sqlite'));a.add_argument('--firm',required=True);a.add_argument('--year',required=True,type=int)
    sub.add_parser('download-sources')
    a=sub.add_parser('collect');a.add_argument('--stock',required=True);a.add_argument('--org',required=True);a.add_argument('--start',required=True);a.add_argument('--end',required=True);a.add_argument('--keyword',default='');a.add_argument('--category',default='');a.add_argument('--output',required=True)
    a=sub.add_parser('extract-section');a.add_argument('--database',default=str(ROOT/'data/derived/distress.sqlite'));a.add_argument('--document',required=True);a.add_argument('--name',required=True);a.add_argument('--start-page',type=int,required=True);a.add_argument('--end-page',type=int,required=True)
    a=sub.add_parser('export');a.add_argument('--database',default=str(ROOT/'data/derived/distress.sqlite'));a.add_argument('--dataset-id',required=True);a.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='download-sources':
        from .acquire import download_verified
        result=download_verified(json.loads((ROOT/'data/raw/records.json').read_text())['documents'],ROOT)
    elif args.command=='collect':
        from .acquire import query
        result={'manifest':str(query(args.stock,args.org,args.start,args.end,args.output,args.keyword,args.category))}
    else:
        con=connect(args.database)
        if args.command=='audit':result=audit_database(con)
        elif args.command=='features':
            from .features import matrices
            result=matrices(con,args.firm,args.year)
        elif args.command=='extract-section':
            from .acquire import extract_section
            result=extract_section(con,ROOT,args.document,args.name,args.start_page,args.end_page)
        elif args.command=='export':
            # Resolve protocol/sample eligibility before downloading a tokenizer.
            protocol=json.loads((ROOT/'configs/protocol.json').read_text())
            if protocol['pending_before_full_dataset']:p.error('Historical sampling frame or event coverage is incomplete; see configs/protocol.json')
            from transformers import AutoTokenizer
            from .dataset import export_dataset
            cfg=json.loads((ROOT/'configs/model.json').read_text())
            tokenizer=AutoTokenizer.from_pretrained(cfg['text_model'],revision=cfg['text_revision'])
            payload=export_dataset(con,tokenizer,args.dataset_id,args.output);result={'rows':len(payload['rows'])}
        con.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
