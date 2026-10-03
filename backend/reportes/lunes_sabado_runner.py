from mail_jobs import run_diario_si_habilitado
from datetime import date, timedelta
import traceback
# Hoy es lunes -> s?bado es hace 2 d?as
hoy = date.today()
# Si hoy es lunes, s?b = hoy -2, si no, calculamos ?ltimo s?bado
# Lunes=0 ... Domingo=6
offset = (hoy.weekday() - 5) % 7  # d?as desde ?ltimo s?bado
if offset == 0:
    sab = hoy
else:
    # si hoy no es s?bado, retroceder
    sab = hoy - timedelta(days=offset)
# Pero para tarea lunes 08:02, hoy ser? lunes, s?bado = hoy -2
# Directo: s?bado = hoy - timedelta(days=2) cuando es lunes
if hoy.weekday() == 0:  # lunes
    sab = hoy - timedelta(days=2)
else:
    sab = hoy - timedelta(days=(hoy.weekday() - 5) % 7)
try:
    r=run_diario_si_habilitado(fecha=sab)
    print(f'OK lunes-sabado {sab} -> filas={r.get("filas")} dest={len(r.get("destinatarios",[]))}')
except Exception as e:
    traceback.print_exc()
    print(f'FAIL {sab} {e}')
