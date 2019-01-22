from subprocess import Popen, PIPE
from datetime import datetime
from math import atan
from socket import gethostname

import sys
import psutil
import time

dBm_color_scale: int = 70  # factor we'll apply to arctan
out = ""
f_white = "\x1b[38;2;255;255;255m"
f_green = "\x1b[38;2;0;255;0m"
f_dark_green = "\x1b[38;2;0;180;0m"
f_red = "\x1b[38;2;255;0;0m"
f_mild_blue = "\x1b[38;2;80;130;210m"
f_darker_gray = "\x1b[38;2;64;64;64m"
f_dark_gray = "\x1b[38;2;128;128;128m"
f_light_gray = "\x1b[38;2;192;192;192m"


# Quick function to get color based on a number (used for wifi dBm)
def wifi_strength(value: int) -> str:
	if value < -110:
		return f"\x1b[38;2;255;0;0m{value} dBm"
	scale = atan((value+110)/dBm_color_scale)
	if scale > 1.0:
		scale = 1.0
	red = 255 - (scale*255)
	green = scale*255
	return f"\x1b[38;2;{int(red)};{int(green)};0m{value} dBm"


def cpu_temperature(value) -> str:
	value = float(value)
	if value >= 70:
		return f"\x1b[38;2;255;0;0m{value}'C"
	if value <= 40:
		return f"\x1b[38;2;0;0;255m{value}'C"
	red = (value-40)*(255/30)
	green = 255-red
	return f"\x1b[38;2;{int(red)};{int(green)};0m{value}'C"


# Get a bool with online/offline from sevice name
def get_service_status(name: str) -> bool:
	p = Popen(["systemctl", "status", name], stdout=PIPE, stdin=PIPE, stderr=PIPE)
	stdout, stderr = p.communicate(timeout=0.1)
	if b"Active: active" in stdout: return True
	else: return False


def get_cpu_text(value: float) -> str:
	green = 255 - (value*2.55)
	red = value*2.55
	return f"\x1b[38;2;{int(red)};{int(green)};0m{value:.1f}"


psutil.cpu_percent(percpu=True)
cpu_start_capture = time.perf_counter()


out += f"{f_light_gray}Welcome, {f_mild_blue}ntoskrnl{f_light_gray}\n\n"

# ----------

boot_dt = datetime.fromtimestamp(psutil.boot_time())
boot_ts = psutil.boot_time()
now_ts = time.time()
updt = now_ts - boot_ts

upseconds = updt  # this will lose us accuracy after 270 years of uptime, should we be worried?
updays = upseconds // 86400
uphours = (upseconds % 86400) // 3600
upminutes = (upseconds % 3600) // 60
upseconds = upseconds % 60

out += f"The time is: {f_green}<replace with datetime> UTC{f_light_gray}\n"
out += f"System uptime is: {f_green}{int(updays):4}d {int(uphours):2d}:{int(upminutes):2d}:{int(upseconds):2d}{f_light_gray}\n"
out += f"Online since {f_green}{boot_dt.__str__()} UTC{f_light_gray}\n\n"

# -----------

out += f"{f_white}System Services{f_dark_gray}\n"
out += f" - {f_green if get_service_status('plexmediaserver') else f_red}plex{f_dark_gray}\n"
out += f" - {f_green if get_service_status('openvpn') else f_red}openvpn{f_dark_gray}\n"

pihole_status = b"Enabled" in Popen(["pihole", "status"], stdin=PIPE, stdout=PIPE, stderr=PIPE).communicate(timeout=0.25)[0]
out += f" - {f_green if pihole_status else f_red}pihole{f_dark_gray}\n"

ps_aux_out = Popen(["ps", "aux"], stdin=PIPE, stdout=PIPE, stderr=PIPE).communicate(timeout=0.2)[0]
out += f" - {f_green if b'gpsd' in ps_aux_out else f_red}gpsd{f_dark_gray}\n"
out += f" - {f_green if b'ntpd' in ps_aux_out else f_red}ntpd{f_dark_gray}\n"

ntbot_status = 0 is not int(open("/home/pi/ntbot/pid", "r").read())
out += f" - {f_green if ntbot_status else f_red}ntoskrnl-bot{f_dark_gray}\n"

arbys_status = 0 is not int(open("/home/pi/arbys/pid", "r").read())
out += f" - {f_green if arbys_status else f_red}Arby's{f_dark_gray}\n\n"

# ----------

out += f"{f_white}Network Interfaces{f_dark_gray}\n"

if_addresses = {x: y[0].address for x, y in psutil.net_if_addrs().items()}
if_status = {x: y.isup for x, y in psutil.net_if_stats().items()}
if_blacklist = ["lo", "tun0", "wlan0"]  # wlan0 in here because we'll add a bit of custom code to get signal strength

for iface, status in if_status.items():
	if iface in if_blacklist: continue
	out += f" - {f_light_gray if status else f_dark_gray}{iface}: {if_addresses[iface] if status else 'offline'}{f_dark_gray}\n"

try:
	if if_status['wlan0']:
		stdout, stderr = Popen(["iwconfig", "wlan0"], stdin=PIPE, stdout=PIPE, stderr=PIPE).communicate(timeout=0.1)
		power = int(stdout.split(b"\n")[5][43:-6])
		out += f" - {f_light_gray}wlan0: {if_addresses[iface]} @ RF strength {wifi_strength(power)}{f_dark_gray}\n"
	else:
		out += f" - {f_dark_gray}wlan0: offline{f_dark_gray}\n"
except KeyError:
	# no wlan0, w/e
	pass

# ----------

out += f"\n{f_white}System Monitors{f_dark_gray}\n"

out += f" - {f_light_gray}CPU Frequency: {f_mild_blue}{psutil.cpu_freq().current} MHz{f_dark_gray}\n"
out += f" - {f_light_gray}CPU Usage: "
out += " ".join([get_cpu_text(x) for x in psutil.cpu_percent(percpu=True)])
out += f"{f_dark_gray}\n"

m_raw = psutil.virtual_memory()
m_total = m_raw.total
m_available = m_raw.available
m_used = m_total - m_available
out += f" - {f_light_gray}Memory Usage: {f_dark_gray}{m_used/(1024*1024):.1f}/{m_total/(1024*1024):.1f} MiB ({(m_used/m_total)*100:.2f}%)\n"

out = out.replace("<replace with datetime>", datetime.fromtimestamp(int(time.time())).__str__())
sys.stdout.write(out)
