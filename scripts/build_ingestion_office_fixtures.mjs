import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile, Presentation, PresentationFile, layers, text, table } from "@oai/artifact-tool";
const out=process.argv[2]; await fs.mkdir(out,{recursive:true});
const wb=Workbook.create();
const s1=wb.worksheets.add("设备信息"); s1.showGridLines=false;
s1.getRange("A1:B6").values=[["字段","值"],["型号","MX-100"],["版本","v1.2"],["温度上限","75℃"],["故障代码","E07"],["日期","2026-07-11"]];
s1.getRange("A1:B1").format={fill:"#17324D",font:{bold:true,color:"#FFFFFF"}};s1.getRange("A:B").format.columnWidth=22;s1.freezePanes.freezeRows(1);
const s2=wb.worksheets.add("故障处理");s2.getRange("A1:C4").values=[["代码","现象","处理"],["E07","温度过高","停止设备并检查散热"],["E02","传感器离线","检查连接"],["E03","电源异常","断电复位"]];s2.getRange("A1:C1").format={fill:"#C9473A",font:{bold:true,color:"#FFFFFF"}};s2.getRange("A:C").format.columnWidth=24;s2.freezePanes.freezeRows(1);
const x=await SpreadsheetFile.exportXlsx(wb);await x.save(path.join(out,"mx100_records.xlsx"));
const xp=await wb.render({sheetName:"设备信息",range:"A1:B6",scale:2,format:"png"});await fs.writeFile(path.join(out,"..","qa_xlsx.png"),new Uint8Array(await xp.arrayBuffer()));
const p=Presentation.create({slideSize:{width:1280,height:720}});const sl=p.slides.add();sl.background.fill="#F7F4ED";
sl.compose(layers({width:"fill",height:"fill"},[
 text(["MX-100 维护说明"],{position:{left:60,top:40},width:1160,height:70,style:{fontSize:"44px",bold:true,color:"#17324D"}}),
 text(["版本 v1.2 | 2026-07-11 | 温度上限 75℃ | 故障代码 E07"],{position:{left:60,top:120},width:1160,height:45,style:{fontSize:"22px",color:"#334E68"}}),
 text(["维护流程：1. 断电  2. 清洁滤网  3. 重启并记录结果\n警告：温度达到75℃时立即停机。"],{position:{left:60,top:190},width:1160,height:110,style:{fontSize:"24px",color:"#111827"}}),
 table({rows:3,columns:3,values:[["代码","现象","处理"],["E07","温度过高","检查散热"],["E02","传感器离线","检查连接"]],columnWidths:[220,340,500],position:{left:90,top:340},width:1060,height:240})
]),{frame:{left:0,top:0,width:1280,height:720},baseUnit:1});
const ppt=await PresentationFile.exportPptx(p);await ppt.save(path.join(out,"mx100_brief.pptx"));
const png=await p.export({slide:sl,format:"png",scale:1});await fs.writeFile(path.join(out,"..","qa_ppt.png"),new Uint8Array(await png.arrayBuffer()));
