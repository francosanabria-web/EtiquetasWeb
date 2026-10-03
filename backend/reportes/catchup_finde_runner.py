from mail_jobs import run_diario_si_habilitado
from datetime import date
import traceback
dates=[date(2026,9,26),date(2026,9,27),date(2026,9,28)]
for d in dates:
    try:
        r=run_diario_si_habilitado(fecha=d)
        print(f'OK {d} -> enviado={r.get("enviado")} filas={r.get("filas")} dest={len(r.get("destinatarios",[]))} asunto={r.get("adjunto")}')
    except Exception as e:
        traceback.print_exc()
        print(f'FAIL {d} {e}')
