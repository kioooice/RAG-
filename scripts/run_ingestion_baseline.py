from __future__ import annotations
import argparse,csv,html,json,sys
from collections import Counter
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT_ROOT))
from src.ingestion.pipeline import process_directory
def main():
 p=argparse.ArgumentParser();p.add_argument("--data-root",type=Path,required=True);p.add_argument("--iteration-dir",type=Path,default=PROJECT_ROOT/"iterations/002_ingestion_baseline");a=p.parse_args();inp=a.data_root/"input";gt=json.loads((a.data_root/"ground_truth.json").read_text(encoding="utf-8"));docs1,units1=process_directory(inp);docs2,units2=process_directory(inp);checks=[]
 def check(name,ok,detail=""): checks.append({"name":name,"passed":bool(ok),"detail":detail})
 by={d["original_filename"]:d for d in docs1}
 for name,e in gt["files"].items(): check(f"route:{name}",by[name]["detected_file_type"]==e["type"]);check(f"status:{name}",by[name]["processing_status"]==e["status"])
 all_text="\n".join(u["text"]+json.dumps(u["structured_data"],ensure_ascii=False) for u in units1)
 for term in gt["required_terms"]: check(f"preserve:{term}",term in all_text)
 for step in gt["steps"]: check(f"step:{step}",step in all_text)
 check("deterministic_document_ids",[d["document_id"] for d in docs1]==[d["document_id"] for d in docs2]);check("deterministic_unit_ids",[u["unit_id"] for u in units1]==[u["unit_id"] for u in units2]);check("no_duplicate_units_second_run",len({u["unit_id"] for u in units2})==len(units2))
 check("word_heading_trace",any(u["source_locator"].get("heading_path") for u in units1 if u["document_id"]==by["mx100_manual.docx"]["document_id"]));check("pdf_page_trace",any(u["source_locator"].get("page")==1 for u in units1 if u["document_id"]==by["mx100_text.pdf"]["document_id"]));check("xlsx_sheet_range",any("sheet" in u["source_locator"] and "cell_range" in u["source_locator"] for u in units1));check("ppt_slide_trace",any("slide" in u["source_locator"] for u in units1));check("tables_structured",any(u["unit_type"]=="table" and u["structured_data"] for u in units1))
 report={"rule_version":"ingestion-rules-v0.1","file_count":len(docs1),"document_record_count":len(docs1),"knowledge_unit_count":len(units1),"status_counts":dict(Counter(d["processing_status"] for d in docs1)),"type_counts":dict(Counter(d["detected_file_type"] for d in docs1)),"ground_truth":{"passed":sum(c["passed"] for c in checks),"total":len(checks),"rate":sum(c["passed"] for c in checks)/len(checks),"checks":checks},"documents":docs1,"representative_units":units1[:12],"deterministic_second_run":all(c["passed"] for c in checks if c["name"].startswith("deterministic") or c["name"].startswith("no_duplicate"))}
 a.iteration_dir.mkdir(parents=True,exist_ok=True);(a.iteration_dir/"parse_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 fields=["file","processing_status","failure_stage","error_or_warning","retryable","recommended_action"]
 with (a.iteration_dir/"failures.csv").open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for d in docs1:
   if d["processing_status"]!="accepted": w.writerow({"file":d["original_filename"],"processing_status":d["processing_status"],"failure_stage":"routing_or_quality","error_or_warning":";".join(d["warnings"]),"retryable":d["processing_status"] in {"needs_ocr","needs_review","failed"},"recommended_action":"OCR separately" if d["processing_status"]=="needs_ocr" else "manual review" if d["processing_status"]=="needs_review" else "skip or add parser"})
 rows="".join(f"<tr><td>{html.escape(d['original_filename'])}</td><td>{d['detected_file_type']}</td><td>{d['processing_status']}</td><td>{d['parser_name']}</td><td>{sum(u['document_id']==d['document_id'] for u in units1)}</td><td>{d['quality_score']}</td><td>{html.escape('; '.join(d['warnings']))}</td></tr>" for d in docs1)
 checks_html="".join(f"<li class={'ok' if c['passed'] else 'bad'}>{'PASS' if c['passed'] else 'FAIL'} - {html.escape(c['name'])}</li>" for c in checks)
 page=f"""<!doctype html><meta charset=utf-8><title>MX-100 ingestion inspection</title><style>body{{font:15px system-ui;margin:36px;color:#18212b}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#17324d;color:white}}.ok{{color:#18794e}}.bad{{color:#b42318}}code{{background:#f1f3f5;padding:2px 5px}}</style><h1>MX-100 多格式资料接入检查</h1><p>文件 {len(docs1)} · KnowledgeUnit {len(units1)} · Ground Truth {report['ground_truth']['passed']}/{report['ground_truth']['total']}</p><h2>文件清单</h2><table><tr><th>文件</th><th>检测类型</th><th>状态</th><th>解析器</th><th>单元数</th><th>质量分</th><th>警告</th></tr>{rows}</table><h2>关键检查</h2><ul>{checks_html}</ul><h2>代表性知识单元</h2><pre>{html.escape(json.dumps(units1[:3],ensure_ascii=False,indent=2))}</pre>""";(a.iteration_dir/"inspection.html").write_text(page,encoding="utf-8");print(json.dumps({k:report[k] for k in ['file_count','knowledge_unit_count','status_counts','type_counts','ground_truth','deterministic_second_run']},ensure_ascii=False,indent=2));return 0 if report['ground_truth']['rate']==1 else 1
if __name__=="__main__":raise SystemExit(main())
