from __future__ import annotations
from datetime import datetime
import io
import pandas as pd

def _sanitize_sheet_name(name: str) -> str:
    for ch in ['\\','/','*','?',':','[',']']:
        name=name.replace(ch,'_')
    return name[:31]

def build_excel_download(sheets: dict[str, pd.DataFrame], metadata: dict|None=None) -> bytes:
    output=io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if metadata:
            pd.DataFrame([{"parameter":k,"value":v} for k,v in metadata.items()]).to_excel(writer, sheet_name="metadata", index=False)
        for name, df in sheets.items():
            safe=_sanitize_sheet_name(name); df.to_excel(writer, sheet_name=safe, index=False); ws=writer.book[safe]; ws.freeze_panes="A2"
            for col in ws.columns:
                max_len=max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
                ws.column_dimensions[col[0].column_letter].width=min(max(max_len+2,10),40)
    output.seek(0); return output.getvalue()

def make_download_filename(prefix: str, scenario_name: str|None=None) -> str:
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{scenario_name}_{stamp}.xlsx" if scenario_name else f"{prefix}_{stamp}.xlsx"
