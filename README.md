<div align="center">

<h1>hitran-mcp</h1>

<p><b>HITRAN 鍏夎氨鏁版嵁搴撶殑 AI 宸ュ叿閾?/b><br>
MCP 鏈嶅姟鍣?+ HitranLink 妗岄潰宸ヤ綔绔?路 瀹炴椂鍙栨暟 路 鏈湴缂撳瓨</p>

<a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="GPLv3"></a>
<a href="https://github.com/LKF0402/hitran-mcp/releases/latest"><img src="https://img.shields.io/github/v/release/LKF0402/hitran-mcp?color=6B8FD4" alt="Release"></a>
<a href="https://github.com/LKF0402/hitran-mcp/releases"><img src="https://img.shields.io/github/downloads/LKF0402/hitran-mcp/total" alt="Downloads"></a>
<img src="https://img.shields.io/badge/Platform-Windows%20x64-0078D6" alt="Platform">
<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB" alt="Python">
<a href="https://github.com/LKF0402/hitran-mcp/stargazers"><img src="https://img.shields.io/github/stars/LKF0402/hitran-mcp?color=yellow" alt="Stars"></a>
<a href="https://github.com/LKF0402/hitran-mcp/issues"><img src="https://img.shields.io/github/issues/LKF0402/hitran-mcp" alt="Issues"></a>
<img src="https://img.shields.io/github/commit-activity/m/LKF0402/hitran-mcp" alt="Commit Activity">
<img src="https://img.shields.io/badge/MCP-stdio-6B8FD4" alt="MCP">
<img src="https://img.shields.io/badge/HITRAN-2024-4C8C4A" alt="HITRAN">
<img src="https://img.shields.io/badge/tools-12-9C6BD4" alt="Tools">
<img src="https://img.shields.io/badge/docs-README-blueviolet" alt="Docs">
[![CI](https://github.com/LKF0402/hitran-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/LKF0402/hitran-mcp/actions/workflows/ci.yml)

</div>

[English](./README.en.md) | 涓枃

---

## 馃殌 蹇€熷紑濮?

**涓ょ浣跨敤鏂瑰紡锛屼换閫夊叾涓€銆?*

| 鏂瑰紡 | 鍓嶇疆鏉′欢 | 涓婃墜鏂瑰紡 |
|---|---|---|
| 馃 **AI 涓€閿儴缃?*锛堟帹鑽愶級 | 鍏峰鏈満鍛戒护鎵ц鑳藉姏鐨?AI 瀹㈡埛绔?| 涓€娆″璇?|
| 馃枼锔?**妗岄潰鐗?* | Windows x64锛屾棤闇€ Python | 瑙ｅ帇鍚庤繍琛?|

### 馃 A 路 灏嗕互涓嬫寚浠や氦缁?AI

> 鍓嶇疆鏉′欢锛欰I 鍔╂墜鍙湪鏈満鎵ц鍛戒护锛圕laude Code / Cursor / Codex / Cherry Studio 鏈湴妯″紡绛夛級銆?

```text
鎴戝湪杩欏彴鐢佃剳涓婁娇鐢?hitran-mcp锛圚ITRAN 鍏夎氨宸ュ叿锛夛紝璇峰畬鎴愬畨瑁呬笌鑷锛屾寜椤哄簭鎵ц锛?
1. 妫€鏌?Python 鏄惁 鈮?3.10锛涘鏋滀笉鏄紝鍛婄煡搴斿畨瑁呯殑鐗堟湰锛屼笉瑕佹敼鍔ㄧ郴缁熷唴鍏朵粬缁勪欢
2. 鍏嬮殕 https://github.com/LKF0402/hitran-mcp 鍒板浐瀹氱洰褰曪紙宸插瓨鍦ㄥ垯鏇存柊锛夛紝鍦ㄨ鐩綍鎵ц pip install -r requirements.txt
3. 杩愯 python tools/hitran_mcp.py --selftest锛屽皢缁撴灉鍘熸牱杩斿洖
4. 鑻ョ幆澧冩敮鎸?MCP 瀹㈡埛绔厤缃紝鎸変粨搴?README銆屾帴鍏?MCP 瀹㈡埛绔€嶆敞鍐屼负 MCP 鏈嶅姟鍣紱涓嶆敮鎸佸垯璺宠繃锛屾敼鐢ㄥ懡浠よ鍏ュ彛 python tools/hitran_cli.py
5. 鐢ㄥ懡浠よ鎵ц涓€涓ず渚嬮獙璇侊細python tools/hitran_cli.py t_spectrum --name CH4 --mole_frac 0.002 --numin 2950 --numax 3100 --T 296 --P 1.01325
6. 鏈€鍚庣敤涓夊彞璇濊鏄庯細鍚庣画鍙洿鎺ョ敤鑷劧璇█鍙戣捣鍝簺璁＄畻銆佹暟鎹紦瀛樹綅缃€佸嚭閿欐椂搴旀煡鐪嬪摢鏉′俊鎭?
```

瀹夎瀹屾垚鍚庯紝鍙洿鎺ヤ互鑷劧璇█鍙戣捣璁＄畻锛屼緥濡傦細**銆岃绠?CH鈧?鍦?2968 cm鈦宦?闄勮繎鐨勫惛鏀惰氨骞剁粯鍥俱€?*

### 馃枼锔?B 路 妗岄潰鐗堬紙鏃犻渶 Python锛?

[**猬囷笍 涓嬭浇鏈€鏂扮増**](https://github.com/LKF0402/hitran-mcp/releases/latest) 鈫?瑙ｅ帇 鈫?杩愯 `HitranLink.exe` 鈫?閫夋嫨鍒嗗瓙涓庡弬鏁?鈫?鐐瑰嚮銆岃绠楀苟缁樺浘銆嶃€?

> 馃挕 **MCP 涓哄彲閫夊舰鎬?*锛氬鎴风鍙墽琛屾湰鍦板懡浠ゆ椂锛孉I 鍙洿鎺ヨ皟鐢?`python tools/hitran_cli.py ...`锛屼笌 MCP 閫氶亾鍏辩敤鍚屼竴寮曟搸銆佺粨鏋滀竴鑷达紱浠呯函缃戦〉瀵硅瘽鐜闇€瑕?MCP銆?

## 馃摳 鏁堟灉棰勮

**HitranLink 妗岄潰宸ヤ綔绔?* 鈥斺€?CH鈧?+ H鈧侽 娣峰悎姘斿惛鏀惰氨锛圕H鈧?2000 ppm銆丠鈧侽 1%锛?96 K銆? atm锛夛細

![HitranLink 涓荤晫闈(docs/images/hitranlink.png)

**鎴潰搴撳湪绾挎绱笌涓€閿笅杞?* 鈥斺€?鎸変腑鏂囧悕妯＄硦鍖归厤鍒嗗瓙銆佸嬀閫?T/P 宸ュ喌鍚庢壒閲忎笅杞斤細

![鎴潰搴撲笅杞界獥鍙(docs/images/xsc-download.png)

## 鉁?鍔熻兘鐗规€?

| 鐗规€?| 璇存槑 |
|---|---|
| 鍏ㄩ摼璺鐩?| 鐗╃鏌ヨ 鈫?绾胯〃鎶撳彇 鈫?寮虹嚎鍒楄〃 鈫?鍚告敹/閫忚繃鐜囪氨 鈫?璋卞浘 鈫?閰嶅垎鍑芥暟 鈫?鎴潰鏂囦欢鍒嗘瀽 |
| 鑼冨洿杈圭晫 | 鍙仛璋辩嚎鍙傛暟涓庡惛鏀惰氨浠跨湡锛圫銆佄炽€佄便€侀€忚繃鐜囥€佹埅闈級锛屼笉娑夊強鍏蜂綋妫€娴嬫妧鏈紙WMS/2f銆丩ITES銆丆RDS 绛夌殑璋冨埗銆佽В璋冦€佷华鍣ㄥ搷搴斾笉鍦ㄦ湰浠撳簱锛?|
| 鍙屽簱妗ユ帴 | 閫愮嚎搴撹蛋 HAPI 鍦ㄧ嚎 API锛涙埅闈㈠簱锛?00+ 閲嶅垎瀛愶級璧板畼鏂?API 鍦ㄧ嚎妫€绱?+ 涓€閿笅杞斤紙鍏?Portal 鐧诲綍锛夛紝鎴栬鍏ユ湰鍦版枃浠讹紝缁熶竴浜х墿閾捐矾 |
| 鐗╃悊闃插憜 | 娣峰悎姘旀寜 `伪_i = x_i 路 伪_pure_i(T, P, 娴存皵)`锛涚獥鍙ｆ湭瑕嗙洊鑷姩閲嶆姄锛? 绾?澶辫触鏄惧紡鎶ラ敊锛屼笉闈欓粯鍑虹┖璋?|
| 鍏ㄧ▼婧簮 | 浠讳綍 CSV/PNG 鍧囧甫 HITRAN2024 鐗堟 + 瀹為檯绾垮瀷 + 娴存皵 + 绾胯〃鍚?+ 鎶撳彇鏃ユ湡 + HAPI/TIPS 鐗堟湰姘村嵃锛屽彲杩芥函鍒板師濮嬫枃鐚紱绾胯〃鏃╀簬瀹樻柟澧為噺鏇存柊鏃惰嚜鍔ㄥ憡璀︼紙瀹樻柟瑕佹眰寮曠敤椤绘敞鏄庢槸鍚︿娇鐢ㄦ洿鏂扮増锛?|
| 璁＄畻缂撳瓨 | 鐩稿悓鍙傛暟鐨勮氨璁＄畻缁撴灉鑷姩缂撳瓨锛?00 鏉′笂闄愶紝LRU 娣樻卑锛夛紝閲嶅璁＄畻鐬椂杩斿洖 |
| 妗岄潰 GUI | HitranLink 宸ヤ綔绔欙細澶氱粍鍒嗗彔鍔犵粯鍥俱€佸浘灞傜鐞嗐€佸己绾垮垪琛紙鏍囨敞鍒嗗瓙鏉ユ簮锛夈€丵(T) 鏇茬嚎銆佹尝闀库啍娉㈡暟鎹㈢畻鍣ㄣ€佹埅闈㈡枃浠跺湪绾挎悳绱笌涓嬭浇銆丆SV/PNG 瀵煎嚭 |
| 瀹夊叏鏇存柊 | 銆屽府鍔?鈫?妫€鏌ユ洿鏂般€嶏細涓嬭浇鍦板潃鎸夊浐瀹氫粨搴?+ 鍥哄畾璧勪骇鍚嶆瀯閫狅紝寮哄埗 SHA-256 涓庡ぇ灏忓弻鏍￠獙锛岄€愭潯瀹夊叏瑙ｅ帇 + 椤跺眰鐧藉悕鍗曪紝鏃ц祫浜х己鎽樿鍒欐嫆缁濊嚜鍔ㄥ崌绾?|
| 璐ㄩ噺闂ㄧ | 62 椤圭绾垮崟鍏冩祴璇曘€丮CP 濂戠害妫€鏌ャ€佸畨鍏?鏁忔劅鎬ф壂鎻忥紱CI 涓夌増鏈煩闃?+ 鐙珛 security job锛涗緷璧栫簿纭攣瀹?+ Dependabot 鍛ㄦ |
| 闆舵暟鎹叆搴?| 缂撳瓨銆佷骇鐗┿€佷釜浜轰笅杞界殑鎴潰鏂囦欢銆佹墦鍖呬骇鐗╁叏閮?gitignore锛屼粨搴撲繚鎸佽交閲?|

## 馃Л 涓夌鐢ㄦ硶鎬庝箞閫?

| 浣跨敤鍦烘櫙 | 鎺ㄨ崘鏂瑰紡 | 鍏ュ彛 |
|---|---|---|
| 浠呴渶璋卞浘涓庢暟鎹鍑?| 妗岄潰鐗?| `HitranLink.exe` |
| 閫氳繃 AI 瀵硅瘽瀹屾垚璁＄畻 | MCP 鏈嶅姟鍣?| 涓嬫柟鎶樺彔鍧椼€屾帴鍏?MCP 瀹㈡埛绔€?|
| 鍙墽琛屾湰鍦板懡浠ゃ€佹殏涓嶉厤缃?MCP | 鍛戒护琛?| `python tools/hitran_cli.py --list` |

涓夎€呭叡鐢ㄥ悓涓€濂楀紩鎿庯紙`tools/hitran.py`锛夛紝缁撴灉涓€鑷淬€?

## 馃摉 椤圭洰姒傝

涓€濂楃墿鐞嗗紩鎿庯紙`tools/hitran.py`锛屽畼鏂?HAPI 1.3.0.0锛夋敮鎾戜笁绉嶇敤娉曪細MCP 鏈嶅姟鍣ㄣ€佸懡浠よ鍏ュ彛銆佹闈㈠伐浣滅珯鈥斺€斿悓涓€缁勫弬鏁帮紝鍚屼竴浠界粨鏋溿€?

鏁版嵁瀹炴椂鍙栬嚜 HITRANonline 鍙屽簱锛堥€愮嚎 + 鎴潰锛夛紱缂撳瓨銆佷骇鐗┿€佹埅闈㈡枃浠躲€佹墦鍖呬骇鐗╁叏閮ㄨ蛋 `.gitignore`锛屼粨搴撳彧鐣欎唬鐮佷笌鏂囨。銆?

<details>
<summary><b>馃 鎺ュ叆 AI锛圡CP / 鍛戒护琛岋級</b></summary>

#### 鈿欙笍 浠庢簮鐮佽锛圡CP锛?

##### 鐜瑕佹眰

- Python 鈮?3.10
- 渚濊禆锛歚hitran-api`锛堝畼鏂?HAPI锛夈€乣numpy`銆乣matplotlib`锛堜粎缁樺浘/璁＄畻鏃舵儼鎬у姞杞斤級

##### 瀹夎

```bash
git clone https://github.com/LKF0402/hitran-mcp.git
pip install -r hitran-mcp/requirements.txt
```

鎴栧皢浠撳簱缃簬浠绘剰鍥哄畾璺緞锛堜笅鏂囦互 `<浠撳簱鐩綍>` 涓轰緥锛夈€?

##### API Key锛堝彲閫夛級

**妗岄潰 GUI**锛欻itranLink 鈫?宸ュ叿 鈫?閰嶇疆 API key 鈫?杈撳叆骞朵繚瀛橈紙鑷姩鍚屾鍒?`Hitran_Data/hitran_api_key.txt` 鍜?HAPI2 `config.json`锛夈€?

**鍛戒护琛?MCP**锛氬埌 [hitran.org](https://hitran.org) 娉ㄥ唽璐﹀彿鑾峰彇 API key锛屽啓鍏?`tools/hitran_api_key.txt`锛堜笌 `hitran_mcp.py` 鍚岀洰褰曪級锛屾垨璁剧疆鐜鍙橀噺 `HITRAN_API_KEY`銆?

> 璇存槑锛氶厤缃?key 鍚庯紝绾胯〃涓嬭浇璧?HITRAN 瀹樻柟 v2 API锛圲RL 鎼哄甫 key锛夛紝鎴潰鏂囦欢娓呭崟锛坄/api/v2/<key>/cross-sections`锛変笌涓嬭浇涔熼渶瑕佸畠锛涙湭閰嶇疆鏃惰嚜鍔ㄥ洖閫€ HAPI 1.x 鏃ф帴鍙ｏ紙璇ユ帴鍙ｄ笉鏍￠獙 key锛夈€傚畼鏂瑰 fetch 鏈夋瘡鏃ラ厤棰濓紝瓒呴檺杩斿洖 403锛涙湰宸ュ叿鑷姩澶嶇敤缂撳瓨锛屼笉閲嶅涓嬭浇銆?

#### 馃 鎺ュ叆 MCP 瀹㈡埛绔?

浠绘剰鏀寔 MCP 鍗忚鐨勫鎴风鍧囧彲銆傚皢 `mcp.config.example.json` 鐨勫唴瀹瑰悎鍏ュ鎴风閰嶇疆锛堥€氬父浣嶄簬璁剧疆涓殑 MCP/宸ュ叿绠＄悊锛夛紝骞?*鏇挎崲涓轰綘鐨勫疄闄呰矾寰?*锛?

```json
"hitran": {
  "command": "python",
  "args": ["D:/hitran-mcp/tools/hitran_mcp.py"],
  "type": "stdio",
  "timeout": 600000,
  "disabled": false
}
```

**Windows 鐢ㄦ埛娉ㄦ剰**锛歚python` 缁忓父涓嶅湪 PATH锛堟垨鎸囧悜 Microsoft Store 绌哄３锛夈€?
> 鍏堝湪缁堢杩愯 `where python` 楠岃瘉锛涙壘涓嶅埌灏卞～瑙ｉ噴鍣ㄥ畬鏁磋矾寰勶紙浣嶄簬鐢ㄦ埛鐩綍涓嬬殑 `python.exe`锛夈€?

淇濆瓨鍚庨噸鍚鎴风锛岀湅鍒?`hitran` 鏈嶅姟鍣ㄤ笌澶氫釜宸ュ叿鍗虫帴鍏ユ垚鍔熴€?

#### 鈱笍 鍛戒护琛屽叆鍙ｏ紙涓嶈 MCP锛?

`tools/hitran_cli.py` 鎶婂悓涓€鎵瑰伐鍏峰嚱鏁版毚闇叉垚鍛戒护琛岋紝涓嶉渶瑕佹敞鍐?MCP 鏈嶅姟鍣ㄣ€備换浣曡兘鎵ц鏈湴鍛戒护鐨?AI 鍔╂墜锛圕laude Code銆丆ursor銆丆odex 绛夛級鎴栬剼鏈兘鍙互鐩存帴璋冪敤锛岀畻鍑虹殑缁撴灉涓?MCP 閫氶亾瀹屽叏涓€鑷淬€?

```bash
# 鍒楀嚭鍏ㄩ儴宸ュ叿锛堝悕绉般€佺敤閫旓級
python tools/hitran_cli.py --list

# 鏌ュ垎瀛?鍚屼綅绱犺〃
python tools/hitran_cli.py t_species --name CH4

# 鍙栫獥鍙ｅ唴鏈€寮?5 鏉＄嚎锛堥€夌嚎/骞叉壈鍒嗘瀽锛?
python tools/hitran_cli.py t_lines --name CH4 --numin 2960 --numax 2975 --top_n 5

# 绠楀惛鏀惰氨锛圕H4 2000 ppm锛?950-3100 cm鈦宦癸紝296 K锛? atm锛?
python tools/hitran_cli.py t_spectrum --name CH4 --mole_frac 0.002 \
    --numin 2950 --numax 3100 --T 296 --P 1.01325

# 閰嶅垎鍑芥暟 Q(T)
python tools/hitran_cli.py t_partition_sum --name CH4 --T 300
```

- 宸ュ叿鍚嶅彲鍐?`hitran_spectrum`锛堜笌 MCP 涓€鑷达級鎴?`t_spectrum`锛堝嚱鏁板悕锛夈€?
- 鍙傛暟鍐欐硶 `--閿?鍊糮锛岄敭鍚嶅嵆鍑芥暟鍙傛暟鍚嶏紱鏁板瓧銆乣true/false`銆丣SON 鏁扮粍浼氳嚜鍔ㄨ瘑鍒€?
- 缁撴灉浠?JSON 鎵撳埌 stdout锛堝簱鏃ュ織璧?stderr锛屼笉姹℃煋杈撳嚭锛夛紝鍔?`--out 缁撴灉.json` 鍙惤鐩樸€?
- 鏀圭敤 MCP 鍓嶆棤闇€浠讳綍杩佺Щ锛氫袱鑰呰皟鐢ㄧ殑鏄悓涓€濂楀嚱鏁般€?

</details>

<details>
<summary><b>馃枼锔?妗岄潰宸ヤ綔绔?/b></summary>

HitranLink 鏄棤闇€缂栫▼鐨勫厜璋卞垎鏋愭闈㈠簲鐢紝閫傚悎鏃ュ父绉戠爺浣跨敤銆?

#### 涓嬭浇涓庤繍琛?

**鏂瑰紡涓€锛氫笅杞介缂栬瘧鐗堟湰锛堟帹鑽愶級**

1. 鍓嶅線 [GitHub Releases](https://github.com/LKF0402/hitran-mcp/releases) 涓嬭浇鏈€鏂扮増鏈殑 `HitranLink-windows-x64.zip`
2. 瑙ｅ帇鍒颁换鎰忕洰褰曪紙璺緞寤鸿涓嶅惈涓枃鍜岀┖鏍硷級
3. 鍙屽嚮 `HitranLink.exe` 鍗冲彲杩愯

> 棣栨杩愯鏃朵細鑷姩鍦ㄧ▼搴忓悓鐩綍鍒涘缓 `Hitran_Data/` 缂撳瓨鐩綍锛岃绠楄繃鐨勭嚎琛ㄤ細鑷姩缂撳瓨锛屼笅娆℃棤闇€閲嶆柊涓嬭浇銆?
>
> 鑻ヨ璁╂墦鍖?GUI 涓庢簮鐮佹ā寮?MCP 鍏辩敤鍚屼竴浠界紦瀛樺拰 API key锛岃缃幆澧冨彉閲?`HITRAN_DATA_DIR` 鎸囧悜鍚屼竴涓暟鎹洰褰曞嵆鍙紱銆岃繍琛岀姸鎬併€嶉〉浼氭樉绀哄疄闄呯紦瀛樻牴涓庡綋鍓嶄唬鐞嗐€?
>
> 鍗囩骇锛氱▼搴忓唴銆屽府鍔?鈫?妫€鏌ユ洿鏂般€嶁啋 鑷姩涓嬭浇骞舵浛鎹€備笅杞藉湴鍧€鐢辩▼搴忔寜鍥哄畾浠撳簱涓庡浐瀹氳祫浜у悕鑷鏋勯€狅紝鏍￠獙 GitHub 鎻愪緵鐨?SHA-256 涓庢枃浠跺ぇ灏忓悗鎵嶈В鍘嬶紝骞跺彧鎺ュ彈椤跺眰 `HitranLink.exe` + `_internal` 鐨勭粨鏋勶紱鏈€鏂拌祫浜х己灏戞憳瑕佹椂鎷掔粷鑷姩鍗囩骇锛屾敼涓烘彁绀烘墜鍔ㄤ笅杞斤紙璇﹁涓嬫柟銆岎煍?瀹夊叏涓庨殣绉併€嶏級銆?

**鏂瑰紡浜岋細浠庢簮鐮佽繍琛?*

```bash
git clone https://github.com/LKF0402/hitran-mcp.git
cd hitran-mcp
pip install -r requirements.txt
python app/hitran_app.py
```

#### 鍔熻兘璇存槑

| 鍔熻兘妯″潡 | 璇存槑 |
|---|---|
| 璋辫绠?| 鏀寔鍚告敹绯绘暟 伪銆佹埅闈?蟽銆佺嚎寮?S(296K)銆侀€忚繃鐜?T 鍥涚杈撳嚭妯″紡 |
| 澶氱粍鍒嗗彔鍔?| 榛樿鍙犲姞缁樺浘锛屽彲鍙犲姞澶氫釜鍒嗗瓙/涓嶅悓宸ュ喌鐨勮氨绾匡紝鍥惧眰鍙崟鐙垹闄?|
| 寮虹嚎鍒楄〃 | 鏄剧ず绐楀彛鍐呮渶寮?N 鏉¤氨绾匡紙谓銆丼銆佄砡air銆丒鈥筹級锛屽鍒嗗瓙鍚堝苟鏃舵爣娉ㄦ瘡鏉＄嚎鏉ユ簮鍒嗗瓙 |
| Q(T) 鏇茬嚎 | 閰嶅垎鍑芥暟闅忔俯搴﹀彉鍖栨洸绾匡紝鐢ㄤ簬璇勪及娓╁害瀵圭嚎寮虹殑褰卞搷 |
| 閰嶅垎鍑芥暟 | 鏌ヨ鎸囧畾娓╁害涓嬬殑 Q(T) 鍊硷紙TIPS-2025锛?|
| 鎴潰鏂囦欢 | 鍦ㄧ嚎鎸変腑鏂囧悕/鍖栧寮忔绱㈡埅闈㈠垎瀛愬苟涓€閿笅杞斤紙鍏?Portal 鐧诲綍锛夛紝璇诲叆鍘熺敓 .xsc / 涓ゅ垪 .txt锛岀粯鍥惧苟瀵煎嚭婧簮 CSV |
| 鎹㈢畻宸ュ叿 | 娉㈤暱 鈫?娉㈡暟瀹炴椂鎹㈢畻鍣?|
| 鍒嗗瓙琛ㄦ煡璇?| HITRAN 瀹樻柟 61 绉嶉€愮嚎鍒嗗瓙琛ㄦ煡璇?|
| 鏁版嵁瀵煎嚭 | 璋卞浘 PNG锛?00 DPI锛夈€佽氨鏁版嵁 CSV锛堝甫婧簮姘村嵃锛夈€佸畬鏁寸嚎琛?CSV |
| 璁＄畻缂撳瓨 | 鐩稿悓鍙傛暟璁＄畻缁撴灉鑷姩缂撳瓨锛岄噸澶嶈绠楃灛鏃惰繑鍥?|
| 鑷姩鏇存柊 | 銆屽府鍔?鈫?妫€鏌ユ洿鏂般€嶏細鍥哄畾浠撳簱 URL銆丼HA-256 + 澶у皬鍙屾牎楠屻€佸畨鍏ㄨВ鍘嬩笌椤跺眰鐧藉悕鍗?|

**鎿嶄綔娴佺▼**锛?
1. 閫夋嫨鍒嗗瓙锛堝彲澶氶€夋贩鍚堟皵锛夈€佹尝鏁扮獥鍙ｃ€佹俯搴︺€佸帇鍔涖€佹闀?
2. 閫夋嫨杈撳嚭妯″紡锛堝惛鏀剁郴鏁?鎴潰/绾垮己/閫忚繃鐜囷級
3. 鐐瑰嚮銆岃绠楀苟缁樺浘銆?
4. 鍙户缁皟鏁村弬鏁板啀娆¤绠楋紝璋辩嚎浼氳嚜鍔ㄥ彔鍔犲埌鍚屼竴鐢诲竷
5. 鐐瑰嚮銆屾竻绌哄浘銆嶉噸缃敾甯冿紝鐐瑰嚮銆屽鍑?CSV/PNG銆嶄繚瀛樼粨鏋?

#### 浠庢簮鐮佹墦鍖?/ 鍙戠増

**鎺ㄨ崘浣跨敤涓€閿彂甯冭剼鏈?* 鈥斺€?瀹冩妸"鎵撳寘 exe"涓?鐢熸垚 zip 璧勪骇"缁戞垚涓€姝ワ紝骞惰嚜鍔ㄦ牎楠屼竴鑷存€э細

```bash
pip install pyinstaller
python tools/build_release.py
```

鑴氭湰鎸夐『搴忓畬鎴愶細

1. 渚濇嵁 `HitranLink.spec` 鎵撳寘 exe锛?
2. 鏇挎崲 `dist/HitranLink/`锛堜繚鐣?exe 渚х嚎琛ㄧ紦瀛樹笌 `hitran_api_key.txt` 鈥斺€?浠呮湇鍔?*鍙戝竷鑰呮湰鏈?*锛屽垏鍕跨洿鎺ュ垎鍙?`dist/` 鐩綍锛夛紱
3. 瀵规墦鍖呬骇鐗╄窇涓€娆℃棤鐣岄潰鑷锛堝垎瀛愭暟 / 璋辩偣鏁?/ 宄板€?/ 涓嬭浇寮曟搸锛夛紱
4. 鐢熸垚 GitHub release 璧勪骇 `dist/HitranLink-windows-x64.zip`锛?*鐧藉悕鍗曞紡**锛氬彧鍚?`HitranLink.exe` + `_internal/`锛孉PI key / 缂撳瓨 / 鏃ュ織涓€寰嬩笉杩?zip锛夛紱
5. **鏍￠獙 zip 鍐呯殑 exe 涓?`dist/HitranLink/HitranLink.exe` 鐨勫ぇ灏忎笌 CRC32 瀹屽叏涓€鑷?*
   鈥斺€?涓嶄竴鑷寸洿鎺ユ姤閿欓€€鍑恒€傝繖鏍峰氨涓嶄細鍐嶅嚭鐜?zip 蹇樹簡閲嶅缓銆佺敤鎴蜂笅杞藉埌鏃х増鏈?鐨勯棶棰樸€?

鍙€夊弬鏁帮細

```bash
python tools/build_release.py --zip-only      # 鍙噸寤?zip锛堟部鐢ㄧ幇鏈?dist锛?
python tools/build_release.py --no-selftest   # 璺宠繃鎵撳寘鍚庣殑鑷
```

鎵撳寘鐩綍绾?245 MB锛坥ne-dir 妯″紡锛屽惈 HAPI2 / sqlalchemy / numba / llvmlite锛夛紝鍘嬬缉鍚?zip 绾?100 MB銆傚彂甯冩椂涓婁紶绗?4 姝ョ敓鎴愮殑 zip 浣滀负 release 璧勪骇鍗冲彲銆?

> 鎵撳寘鍓嶈鍏抽棴鎵€鏈夋鍦ㄨ繍琛岀殑 HitranLink 绐楀彛锛屽惁鍒欎細鍥犳枃浠堕攣瀹氬け璐ワ紙鑴氭湰浼氱粰鍑烘槑纭彁绀猴級銆?
>
> **涓嶈鎵嬪啓 `pyinstaller` 鍛戒护**锛歚HitranLink.spec` 涓寘鍚?HAPI2 / sqlalchemy / numba /
> llvmlite / pyparsing 绛夊繀闇€渚濊禆锛屾墜鍐欏弬鏁版瀬鏄撴紡鎺夛紝瀵艰嚧鎵撳寘鐗?HAPI2 涓嶅彲鐢ㄣ€?

</details>

<details>
<summary><b>馃梻锔?浠撳簱缁撴瀯涓庢墦鍖?/b></summary>

```
hitran-mcp/
鈹溾攢 README.md                 # 涓枃鏂囨。锛堟湰鏂囦欢锛?
鈹溾攢 README.en.md              # English documentation
鈹溾攢 docs/
鈹? 鈹溾攢 images/                # README 閰嶅浘锛堢晫闈㈡埅鍥撅級
鈹? 鈹斺攢 QUALITY_AUDIT.md       # 鍒嗙淮搴﹁川閲忚瘎浼颁笌鏁忔劅鎬ф娴嬫姤鍛?
鈹溾攢 CHANGELOG.md              # 鏇存柊鏃ュ織
鈹溾攢 SECURITY.md               # 瀹夊叏鏀跨瓥涓庢紡娲炴姤鍛婃笭閬?
鈹溾攢 LICENSE                   # GPLv3 鍗忚
鈹溾攢 requirements.txt          # Python 渚濊禆锛堢簿纭攣瀹氱増鏈級
鈹溾攢 requirements-py313.txt    # Python 3.13 鍚屽悕閿佸畾锛坣umpy 2.1.3 / matplotlib 3.10.0锛?
鈹溾攢 mcp.config.example.json   # MCP 瀹㈡埛绔敞鍐岀墖娈碉紙鏀硅矾寰勫悗鍚堝叆浣犵殑閰嶇疆锛?
鈹溾攢 HitranLink.spec            # PyInstaller 鎵撳寘瑙勬牸
鈹溾攢 .github/
鈹? 鈹溾攢 workflows/ci.yml       # CI锛氫笁鐗堟湰鐭╅樀 + 鍗曞厓/濂戠害/瀹夊叏 job
鈹? 鈹斺攢 dependabot.yml         # pip 涓?Actions 渚濊禆鍛ㄦ
鈹溾攢 app/
鈹? 鈹溾攢 hitran_app.py          # HitranLink 妗岄潰宸ヤ綔绔欙紙Tkinter + matplotlib GUI锛?
鈹? 鈹溾攢 updater.py             # 鑷姩鏇存柊瀹夊叏鍘熻锛圲RL 鐧藉悕鍗?SHA-256/瀹夊叏瑙ｅ帇锛?
鈹? 鈹溾攢 __init__.py
鈹? 鈹斺攢 hitranlink.ico          # 搴旂敤鍥炬爣
鈹溾攢 tests/
鈹? 鈹溾攢 test_updater.py        # 鏇存柊閾捐矾鍗曞厓娴嬭瘯
鈹? 鈹溾攢 test_core.py           # 鑴辨晱銆佹枃浠跺悕闃查€冮€搞€佺姸鎬佸瓧娈垫祴璇?
鈹? 鈹溾攢 test_data_version.py   # 绾胯〃鐗堟鍙拌处 / 鎽╁皵鍒嗘暟鎶ゆ爮 / specs_csv 娴撳害鏍囧織
鈹? 鈹溾攢 test_mcp_ai.py         # MCP 閿欒濂戠害 / 鏇茬嚎閲囨牱 / 骞叉壈鍒ょ骇 / 缁勫垎鏍囩涓?蟽鈥撓?鍥炲綊
鈹? 鈹斺攢 test_cli.py            # 鍛戒护琛屽叆鍙ｆ祴璇?
鈹斺攢 tools/
   鈹溾攢 hitran_mcp.py          # MCP 鏈嶅姟鍣ㄦ湰浣擄紙stdio JSON-RPC锛岀函鏍囧噯搴擄級
   鈹溾攢 hitran_cli.py          # 鍛戒护琛屽叆鍙ｏ紙涓嶈 MCP 涔熻兘璋冪敤鍚屼竴鎵瑰伐鍏峰嚱鏁帮級
   鈹溾攢 hitran.py              # 瀹樻柟 HAPI 鐨勭粺涓€钖勫皝瑁咃紙杈撳叆鎶ゆ爮 + 婧簮姘村嵃 + 璁＄畻缂撳瓨锛?
   鈹溾攢 contract_check.py      # 绂荤嚎濂戠害妫€鏌ワ紙14 宸ュ叿 / 鍗忚 / BOM锛?
   鈹溾攢 security_check.py      # 瀹夊叏涓庢晱鎰熸€ф壂鎻忥紙鍙戝竷鍓嶉椄闂級
   鈹溾攢 build_release.py       # 涓€閿墦鍖?+ 鍑?zip + 涓€鑷存€ф牎楠?+ 瀹夊叏闂搁棬
   鈹斺攢 __init__.py
```

杩愯鏈熻嚜鍔ㄧ敓鎴愶紙鍙殢鏃跺垹闄わ紝鐢卞伐鍏烽噸鐢燂級锛?

- `Hitran_Data/` 鈥?绾胯〃缂撳瓨
- `tmp/mcp_out/` 鈥?MCP 宸ュ叿浜х墿锛圕SV/PNG锛岃嚜甯︽函婧愭按鍗帮級
- `tmp/` 鈥?妗岄潰宸ヤ綔绔欎复鏃舵枃浠朵笌鑷祴杈撳嚭
- `xsc_data/` 鈥?鐢ㄦ埛鎸夐渶涓嬭浇鐨勬埅闈㈡枃浠讹紙涓汉鏁版嵁锛屼笉鍏ュ簱锛?
- `dist/` / `build/` 鈥?PyInstaller 鎵撳寘浜х墿锛堜笉鍏ュ簱锛?

</details>

<details>
<summary><b>馃П 鏁版嵁鏋舵瀯</b></summary>

HITRAN2024 閲囩敤**鍙屽簱鍒嗗彂鏋舵瀯**锛屼袱鏉℃暟鎹€氶亾鐨勮闂満鍒朵笉鍚屸€斺€旇繖涔熸槸"鏌愮墿绉嶅湪閫愮嚎宸ュ叿涓煡涓嶅埌"鐨勬牴鍥犮€?

#### 閫愮嚎搴擄紙LBL锛?

- 瑕嗙洊 **61 绉嶅垎瀛?*锛圚鈧侽 / CO鈧?/ CH鈧?/ C鈧侶鈧?/ N鈧侽鈥︼級鍙?130+ 鍚屼綅绱犱綋锛屾暟鎹负**閫愯穬杩佺嚎鍙傛暟**锛埼? S, 纬_air, E鈥斥€︼級銆?
- 瀛樺偍浜?HITRANonline 鍏崇郴鍨嬫暟鎹簱锛岀粡瀹樻柟 **HAPI**锛圚ITRAN Application Programming Interface锛孠ochanov et al., JQSRT 177, 15鈥?0, 2016锛?*鍦ㄧ嚎 API** 鎻愪緵鈥斺€斿搴旀湰 MCP 鐨?`hitran_fetch / lines / spectrum / plot` 閫氶亾锛氬疄鏃跺彇鏁般€佹湰鍦扮紦瀛樸€佸彲澶嶇幇銆?

#### 鎴潰搴擄紙XSC锛?

- 瑕嗙洊 **600+ 閲嶅垎瀛?*锛堢兎鐑冦€乂OC銆佸埗鍐峰墏绛夛級锛氬涓虹瀵嗘尟鍔ㄥ甫缁撴瀯銆佺己涔忛€愮嚎楠岃瘉鍙傛暟锛屼互**娴嬮噺鍏夎氨鏂囦欢**鏀跺綍鈥斺€斿師鐢?`.xsc`锛? 琛屽畾瀹藉ご + 蟽 搴忓垪锛屽崟浣?cm虏/molecule锛夋垨涓ゅ垪 谓鈥撓?鏂囨湰锛堝崟浣?cm鈦宦?/ cm虏路molecule鈦宦癸級銆?
- 璁块棶鏈哄埗锛氬畼鏂?v2 API锛坄/api/v2/<key>/cross-sections`锛夋彁渚?*鏂囦欢娓呭崟**锛屽叕寮€鏁版嵁璺緞 `/data/xsec/` 鎻愪緵**鏂囦欢鏈綋**锛屼簩鑰呭潎鍙洿鎺ヨ闂€?*鏃犻渶鐧诲綍 Web Portal**锛堥渶鏈満閰嶇疆 HITRAN API key锛夈€侶API 1.x 渚т粎鎻愪緵 `read_hotw()` 鏈湴璇绘枃浠舵帴鍙ｃ€?

#### 鍙屽簱妗ユ帴

- 閫愮嚎閫氶亾锛堥€愯穬杩佸弬鏁帮級涓庢埅闈㈤€氶亾锛堟祴閲忓厜璋憋級鏄袱濂楁暟鎹粨鏋勶紝HITRAN 瀹樻柟鍒嗗紑鍒嗗彂锛涙湰宸ュ叿鎶婂畠浠粺涓€鍒板悓涓€鏉′骇鐗╅摼璺€?
- **涓€閿笅杞斤紙鎺ㄨ崘锛屽厤 Portal 鐧诲綍锛?*锛?
  1. `hitran_xsc_molecules(query="涓欑兎")` 妫€绱㈠垎瀛愬苟鎷垮埌 `id`锛堟敮鎸佷腑鏂囧悕/鍖栧寮?鑻辨枃鍚?淇楀悕锛夛紱
  2. `hitran_xsc_files(molecule_id=<id>)` 鍒楀嚭鍙洿鎺ヤ笅杞界殑鏂囦欢锛圱/P/娉㈡暟鑼冨洿/鐐规暟/浣撶Н锛夛紱
  3. `hitran_xsc_download(name=..., filenames=[...])` 涓嬭浇鍒?`xsc_data/`锛坓itignore锛屼笉鍏ュ簱锛涢粯璁や笂闄?300 MB锛夛紱
  4. `hitran_cross_section(file_path=...)` 璇诲叆锛屽畬鎴愭埅绐椼€佺粯鍥俱€佹函婧?CSV 瀵煎嚭锛屼笌閫愮嚎璋卞叡鐢?`tmp/mcp_out/` 浜х墿閾捐矾銆?
- **鎵嬪姩涓嬭浇锛堟棤 API key 鏃讹級**锛歚hitran_xsc_search(name=...)` 鍏嶇櫥褰曟帰娴嬫竻鍗?鈫?鑷?hitran.org/xsc 涓嬭浇鏂囦欢鏀惧叆 `xsc_data/` 鈫?`hitran_cross_section` 璇诲叆銆?
- 閫愮嚎宸ュ叿閬囧埌鎴潰搴撴敹褰曠殑鍒嗗瓙鏃讹紝鎶ラ敊淇℃伅浼氭樉寮忔彁绀鸿鏋舵瀯宸紓涓庢纭矾寰勩€?

</details>

<details>
<summary><b>馃搵 宸ュ叿鍙傝€冿紙14 涓級</b></summary>

> AI 璋冪敤寤鸿锛氬厛鐢?`hitran_interference` 鍒よ繖鏉＄嚎鑳戒笉鑳界敤锛屽啀鐢?`hitran_report` 涓€瓒熸嬁鍏紙璋?鍥?寮虹嚎锛夈€傞渶瑕佺粏绮掑害鎺у埗鍐嶆媶鐢?`hitran_lines` / `hitran_spectrum` / `hitran_plot`銆?
> 澶辫触鏃惰繑鍥?`{"error": {"code", "message", "hint"}}`锛歚E_BAD_ARGS` / `E_STRICT` / `E_NO_LINES` / `E_WINDOW_UNCOVERED` / `E_UPSTREAM_403` / `E_UPSTREAM_429` / `E_MISSING_FILE` / `E_UNKNOWN_TOOL` / `E_INTERNAL`锛屾寜 `hint` 鍐冲畾涓嬩竴姝ワ紝涓嶈閲嶈瘯鍚屼竴缁勯敊璇弬鏁般€?

| 宸ュ叿 | 鐢ㄩ€?| 鍏抽敭杈撳叆 |
|---|---|---|
| `hitran_species` | 瀹樻柟鍒嗗瓙琛細鍒嗗瓙鍙?M銆佷富鍚屼綅绱犮€佸悇鍚屼綅绱犺嚜鐒朵赴搴︿笌璐ㄩ噺 | `name`锛堝垎瀛愬紡鎴栧垎瀛愬彿锛岀渷鐣ヨ繑鍥炲叏琛級 |
| `hitran_fetch` | 鎶撳彇娉㈡暟绐楀彛绾胯〃鍒版湰鍦扮紦瀛橈紱鏈鐩栫獥鍙ｈ嚜鍔ㄩ噸鎶?| `name`, `numin`, `numax`, `iso` |
| `hitran_lines` | 绐楀彛鍐呮渶寮?N 鏉＄嚎锛埼姐€丼銆佄砡air銆丒鈥筹級锛岄€夌嚎/骞叉壈鍒嗘瀽 | `name`, `numin`, `numax`, `top_n` |
| `hitran_spectrum` | 鍚告敹绯绘暟 伪 / 閫忚繃鐜囪氨锛孋SV 甯︽函婧愭按鍗帮紱澶氱墿绉嶅彲鐢?`specs_csv` 涓€娆″彔鍔狅紱`sample_points>0` 鏃跺洖浼犻噰鏍锋洸绾夸緵璇昏氨褰?| `specs_csv` 鎴?`name`锛沗numin`, `numax` 蹇呭～ |
| `hitran_plot` | 璋卞浘 PNG锛堝鐗╃鍙犲姞 + 鎬昏氨锛宍ylog` 鍙€夛級 | 鍚?`hitran_spectrum`锛屽彟鍔?`title/ylog/dpi` |
| `hitran_report` | **AI 棣栭€?*锛氫竴娆¤皟鐢ㄦ嬁鍏?鈥斺€?宄板€?+ 閲囨牱鏇茬嚎 + 寮虹嚎娓呭崟 + PNG/CSV + 鏁版嵁鐗堟 + 鍛婅 + `next_actions` | `name` 鎴?`specs_csv`锛沗numin`, `numax`锛涘彲閫?`top_n/sample_points/make_plot` |
| `hitran_interference` | **閫夌嚎鍒ゆ嵁**锛氱洰鏍囩嚎涓績鐨勪氦鍙夊共鎵版瘮鍊硷紙鍚勫共鎵扮粍鍒?伪銆乺atio銆乨B銆佺獥鍐呮渶澶ф瘮鍊笺€佸悎璁″垽绾?negligible/minor/significant/dominant锛?| `name`, `interferers_csv`锛?H2O:0.01,CO2:4e-4'锛夛紱`numin`, `numax`锛涘彲閫?`line_index/half_width/T/P` |
| `hitran_partition_sum` | 閰嶅垎鍑芥暟 Q(T)锛孴IPS 2025/2021/2017/2011 鍙€?| `name` 鎴?`M`锛沗T` |
| `hitran_cross_section` | 璇诲叆鏈湴鎴潰鏂囦欢锛堝師鐢?`.xsc` 鎴?谓鈥撓?涓ゅ垪锛夆啋 鎴獥/缁樺浘/婧簮 CSV | `file_path`锛堢己鐪佹椂鍒楀嚭 `xsc_data/` 鍙敤鏂囦欢锛?|
| `hitran_xsc_search` | 鍦ㄧ嚎鎺㈡祴鎴潰瀛愬簱鍒嗗瓙鐨勬埅闈㈡枃浠舵竻鍗曪紙鍏嶇櫥褰曞彧璇伙紝鏃犳枃浠跺悕锛?| `name`锛圥ortal 鏄剧ず鍚嶏級 |
| `hitran_xsc_molecules` | 鎴潰鍒嗗瓙妫€绱細涓枃鍚?鍖栧寮?鑻辨枃鍚?淇楀悕妯＄硦鍖归厤锛岃繑鍥炲€欓€変笌 `id`锛堢害 670 涓垎瀛愶級 | `query`锛堢暀绌哄垪鍏ㄩ儴锛夛紱`limit` |
| `hitran_xsc_files` | 鍒楀嚭鏌愭埅闈㈠垎瀛?*鍙洿鎺ヤ笅杞?*鐨勬枃浠舵竻鍗曪紙T/P/娉㈡暟鑼冨洿/鍒嗚鲸鐜?鐐规暟/浣撶Н浼扮畻/filename锛岄渶 API key锛?| `name` 鎴?`molecule_id`锛沗include_all` |
| `hitran_xsc_download` | 閫夊畾鏂囦欢涓嬭浇鍒?`xsc_data/`锛堝畼鏂?API + 鍏紑鏁版嵁璺緞锛屽厤 Portal 鐧诲綍锛岄粯璁や笂闄?300 MB锛?| `name`, `filenames`/`ids`锛沗dry_run`, `overwrite`, `max_total_mb` |
| `hitran_apikey_status` | API key / 缂撳瓨 / 浜х墿 / 鎴潰鏂囦欢鐘舵€侀€熸煡 | 鈥?|

澶氱墿绉嶅彔鍔犵ず渚嬶紙`specs_csv`锛屼笌 `name` 浜掓枼锛夛細

```
hitran_spectrum(specs_csv="CH4:0.01,C2H6:1e-5", numin=2950, numax=3120, T=296, P=1.0)
```

</details>

<details>
<summary><b>馃搹 浣跨敤瑙勮寖涓庡畨鍏?/b></summary>

#### 馃搹 浣跨敤瑙勮寖

1. **鍗曚綅**锛氶粯璁よ繑鍥炲惛鏀剁郴鏁?伪锛坈m鈦宦癸級锛沗hitran_units=true` 杩斿洖鎴潰 蟽锛坈m虏/molecule锛夛紝**涓ょ鍙ｅ緞閮芥寜鎽╁皵鍒嗘暟鍔犳潈**锛埼盻i=x_i路伪_pure锛屜僟i=x_i路蟽_pure锛夛紝娣峰悎姘旀€婚噺鍗虫贩鍚堢墿鍙ｅ緞銆?br>`mode=transmittance` 涓?`hitran_units=true` 鏃讹紝蟿=exp(鈭捪兟種路L)锛孨=P/(k_BT)锛堢悊鎯虫皵浣擄紝杩斿洖 `number_density_cm-3`锛夛紱伪 鍙ｅ緞涓?蟿=exp(鈭捨甭稬)銆?
2. **娣峰悎姘?*锛毼?涓?蟽 鍚屼竴鏉¤鍒欌€斺€旀寜 `伪_i = x_i 路 伪_pure_i(T, P, 娴存皵)`銆乣蟽_i = x_i 路 蟽_pure_i` 璁＄畻锛屼笉浣跨敤 `x路P` 浣滀负鍒嗗帇锛涙湭鎻愪緵娴撳害鏃舵寜绾皵浣撹绠楀苟鎻愮ず纭銆傚悓涓€鍒嗗瓙澶氱粍鍒嗭紙濡備笉鍚屽悓浣嶇礌锛夊悇鑷嫭绔嬭鍏?total锛屾爣绛惧甫 `[I=鈥` 鍚庣紑锛屼笉浼氫簰鐩歌鐩栥€?
3. **鍙傛暟婢勬竻**锛氭湭缁欏嚭鍙傛暟浣跨敤榛樿鍊煎苟濡傚疄鍒楀嚭锛坄needs_confirm=true` 鏃堕渶鍚戠敤鎴峰鏍?T/P/绐楀彛/娴撳害锛夛紱`strict=true` 鏃?T/P 缂哄け鐩存帴鎶ラ敊銆?
4. **绾垮瀷**锛歚profile` 鍙€?voigt锛堥粯璁わ級/ lorentz / gauss / doppler / ht / sdvoigt锛屽叏閮ㄧ洿璋冨畼鏂?HAPI 璋卞嚱鏁般€俙mht`锛坢odified Hartmann-Tran锛孒ITRAN2024 鎺ㄨ崘锛変笌 `qsdhc` 鐩墠涓嶅彲閫夛細涓婃父 HAPI 1.3.0.0 / hapi2 0.2.1 鍧囨湭鎻愪緵鍏跺惛鏀剁郴鏁版帴鍙ｏ紝绋嬪簭浼氭樉寮忔姤閿欏苟寤鸿鏀圭敤 `ht` / `sdvoigt`锛屼笉鍋氭湭缁忛獙璇佺殑寮鸿瀹炵幇銆?
5. **婧簮**锛氫换浣?CSV/鍥惧潎鍙拷婧嚦 HITRAN2024锛圙ordon et al., JQSRT 2026, doi:10.1016/j.jqsrt.2026.109807锛? HAPI锛圞ochanov et al., JQSRT 2016锛? TIPS 鐗堟湰锛涜鏂囧紩鐢ㄤ互杩斿洖鐨?citation 瀛楁涓哄噯銆傛按鍗板彟璁板疄闄呯嚎鍨嬨€佹荡姘斻€佺嚎琛ㄥ悕涓庢姄鍙栨棩鏈燂紙`# data: ... table fetched ...`锛夆€斺€斿畼鏂硅姹傚紩鐢ㄦ椂娉ㄦ槑鏄惁浣跨敤鏇存柊鐗堬紱鎶撳彇鏃ユ湡鏃╀簬鏈€杩戜竴娆″畼鏂规洿鏂版壒娆℃椂鍐欏叆 `# WARN` 骞跺湪 `warnings` 涓彁绀恒€?
6. **鍚屼綅绱犲彛寰?*锛氶粯璁や富鍚屼綅绱狅紙绾皵浣撴潈閲?1.0锛夛紱`iso="all"` 鎸夊畼鏂硅嚜鐒朵赴搴﹀姞鏉冦€?

#### 馃敀 瀹夊叏涓庨殣绉?

**鏁版嵁闈?*锛氭湰椤圭洰鍙仛 HITRAN 鍙栨暟涓庢湰鍦板厜璋辫绠楋紝涓嶉噰闆嗛仴娴嬨€佷笉涓婃姤浣跨敤鏁版嵁锛涘敮涓€鐨勫嚟鎹槸 HITRAN API key銆?

**鍑嵁瀛樻斁**锛欰PI key 鍙惤鍦ㄨ繍琛屾湡鏁版嵁鐩綍锛坄Hitran_Data/hitran_api_key.txt`锛屽凡 gitignore锛夈€傛煡璇紭鍏堢骇涓虹幆澧冨彉閲?`HITRAN_API_KEY` > `tools/hitran_api_key.txt` > `Hitran_Data/hitran_api_key.txt`銆傚彂甯?ZIP 涓嶅惈 key銆佺紦瀛樹笌鏃ュ織銆?

**鑷姩鏇存柊**锛?

- 涓嬭浇鍦板潃鐢辩▼搴忔寜 `LKF0402/hitran-mcp` + 鍥哄畾璧勪骇鍚?`HitranLink-windows-x64.zip` 鏋勯€狅紝涓嶄俊浠?API 杩斿洖鐨勪换鎰忛摼鎺ワ紱鍙帴鍙?`https://github.com/...` 鍓嶇紑锛屾嫆缁?http銆佸紓鍩熶富鏈轰笌鏌ヨ涓层€?
- 涓嬭浇鏃惰竟鍐欒竟绠?SHA-256锛屽悓鏃舵牎楠?GitHub 鎻愪緵鐨?`digest` 涓?`size`锛涗换涓€涓嶇鍗冲垹闄ゅ崐鎴枃浠跺苟涓銆?
- 瑙ｅ帇閫愭潯鎷掔粷缁濆璺緞銆佺洏绗︺€乣..`銆佺鍙烽摼鎺ヤ笌鍔犲瘑鏉＄洰锛岄檺鍒舵潯鐩暟锛?0000锛変笌瑙ｅ帇鎬婚噺锛?00 MB锛夛紱椤跺眰鍙厑璁?`HitranLink.exe` 涓?`_internal`銆?
- 鏃х増鏈祫浜ц嫢娌℃湁 `digest`锛岀▼搴忔嫆缁濊嚜鍔ㄥ崌绾у苟鎻愮ず鎵嬪姩涓嬭浇鈥斺€旇繖鏄湁鎰忕殑瀹夊叏闄嶇骇銆?

**鍙戝竷闂搁棬**锛歚tools/build_release.py` 鍦ㄥ嚭鍖呭墠璋冪敤 `tools/security_check.py`锛屾壂鎻忚窡韪枃浠躲€丟it 鍘嗗彶銆佸伐浣滃尯涓庡彂甯?ZIP 涓殑鍑嵁/涓汉璺緞/鍗遍櫓璋冪敤锛屽嚭鐜伴樆鏂」鐩存帴鎷掔粷鍑哄寘锛汣I 鍙﹁鐙珛 security job 澶嶆煡銆?

**杩愯鎻愮ず**锛歐indows 浜岃繘鍒舵湭鍋氫唬鐮佺鍚嶏紝棣栨杩愯濡傚嚭鐜?SmartScreen 鎻愮ず锛屽彲閫夋嫨銆屾洿澶氫俊鎭?鈫?浠嶈杩愯銆嶃€?

婕忔礊鎶ュ憡鏂瑰紡瑙?[SECURITY.md](SECURITY.md)銆?

</details>

<details>
<summary><b>鉁?娴嬭瘯涓庤川閲忛棬绂?/b></summary>

| 妫€鏌?| 鍛戒护 | 瑕嗙洊鑼冨洿 | 鏈熸湜 |
|---|---|---|---|
| 鍗曞厓娴嬭瘯 | `python -m unittest discover -s tests -v`锛堟垨 `python -m pytest -q`锛?| 鏇存柊鍦板潃鐧藉悕鍗曘€丼HA-256銆佸畨鍏ㄨВ鍘嬶紙`../`銆佺粷瀵硅矾寰勩€佺洏绗︺€亃ip bomb銆佺鍙烽摼鎺ワ級銆侀《灞傜櫧鍚嶅崟銆佽劚鏁忎笌鏂囦欢鍚嶉槻閫冮€搞€佹暟鎹増娆″彴璐︼紙绾垮瀷/鎶撳彇鏃ユ湡/闄堟棫鍛婅锛夈€佹懇灏斿垎鏁版姢鏍忋€丮CP 閿欒鐮併€佹洸绾块噰鏍枫€乺eport 缁勮銆佸共鎵版瘮鍒ょ骇锛涚粍鍒嗘爣绛惧敮涓€鍖栥€佅?鍙ｅ緞鍔犳潈銆佅冣€撻€忚繃鐜囨暟瀵嗗害銆佸師鐢?.xsc 浼樺厛瑙ｆ瀽銆佺紦瀛樻牴璺熼殢鏁版嵁鐩綍 | 62/62 閫氳繃 |
| MCP 濂戠害 | `python tools/contract_check.py` | 14 涓伐鍏风殑 `TOOLS`/`DISPATCH` 涓€鑷存€с€乻chema 蹇呭～銆乣initialize`/`tools/list`/`ping` 杩斿洖銆佹棤 UTF-8 BOM | `{"ok": true, "tools": 14, "version": "1.7.5"}` |
| 瀹夊叏/鏁忔劅鎬?| `python tools/security_check.py` | 璺熻釜鏂囦欢銆丟it 鍘嗗彶銆佸伐浣滃尯銆佸彂甯?ZIP銆丳ython AST 鍗遍櫓璋冪敤銆佷緷璧栭攣瀹氥€乣.gitignore` 瑕嗙洊 | `"ok": true`銆乣issues: []` |
| MCP 鑱旂綉鑷祴 | `python tools/hitran_mcp.py --selftest` | 鐪熷疄鎶撳彇 CO 灏忕獥鍙ｅ苟鐢熸垚鍥惧儚锛屽彟鍚埅闈㈤摼璺紙鍚堟垚鏂囦欢锛夈€佸湪绾挎帰娴嬩笌鐘舵€佹鏌?| 鍏ㄩ摼璺垚鍔?|
| 妗岄潰宸ヤ綔绔欒嚜娴?| `python app/hitran_app.py --selftest selftest.json` | 寮曟搸 + 鏁版嵁 + 缃戠粶鍦ㄦ墦鍖呯幆澧冨唴鍙敤锛岃緭鍑哄垎瀛愭暟銆佽氨鐐规暟銆佸嘲鍊笺€亀arnings | `warnings: []` |

CI锛坄.github/workflows/ci.yml`锛夊湪 Windows 涓婅窇 Python 3.10/3.11/3.12 涓夌増鏈煩闃碉細璇硶缂栬瘧銆乣pyflakes` 闈欐€佹鏌ャ€佸崟鍏冩祴璇曘€佸绾︽鏌ワ紱鍙︽湁 `fetch-depth: 0` 鐨?security job 鎵弿 Git 鍘嗗彶銆備緷璧栧湪 `requirements.txt` 绮剧‘閿佸畾锛坄hitran-api==1.3.0.0`銆乣numpy==2.0.1`銆乣matplotlib==3.9.1`銆乣Pillow==11.0.0`锛夛紝鐢?Dependabot 姣忓懆妫€鏌ユ洿鏂帮紱Python 3.13 鍙︾敤 `requirements-py313.txt`锛堝悓鍙ｅ緞绮剧‘閿佸畾锛宯umpy 2.1.3 / matplotlib 3.10.0锛夛紝鍥?2.0.1 / 3.9.1 鏃?3.13 杞瓙銆?

鍒嗙淮搴﹁瘎鍒嗕笌鏁忔劅鎬ф娴嬫槑缁嗚 [docs/QUALITY_AUDIT.md](docs/QUALITY_AUDIT.md)銆?

</details>

<details>
<summary><b>鉂?甯歌闂</b></summary>

- **鎶撳彇澶辫触 "daily limit"**锛氬畼鏂规瘡鏃ラ厤棰濊秴闄愶紝娆℃棩閲嶈瘯锛涚紦瀛樻湭鍒犳椂澶ч儴鍒嗙獥鍙ｆ棤闇€閲嶆柊鎶撳彇銆?
- **鎶ラ敊 "Cannot connect to http://hitran.org" 鎴?鏃犳硶鎶撳彇"锛屼絾璇ュ垎瀛愬湪姝ょ獥鍙ｆ槑鏄庢湁鍚告敹**锛氳繖鏄?*鑱旂綉澶辫触**锛屼笌"璇ョ獥鍙ｆ棤鏀跺綍绾?鏃犲叧銆傛渶甯歌鍘熷洜鏄幆澧冨彉閲?`HTTP_PROXY` / `HTTPS_PROXY` 鎸囧悜鐨勪唬鐞嗕笉鍙敤锛堜緥濡?VPN 鍏抽棴鏃剁殑 `127.0.0.1:7892`锛夆€斺€斿紑鍚唬鐞?VPN锛屾垨娓呯┖璇ョ幆澧冨彉閲忚蛋鐩磋繛鍚庨噸璇曞嵆鍙紙鑱旂綉鎭㈠鍚庝細鑷姩閲嶆姄锛夛紱宸茬紦瀛樿繃鐨勫垎瀛?绐楀彛鍙绾胯绠椼€?
- **淇敼浠ｇ爜涓嶇敓鏁?*锛氶噸鍚?AI 瀹㈡埛绔紙MCP 杩涚▼闅忓鎴风鍚姩锛夛紱妗岄潰宸ヤ綔绔欓渶閲嶅惎绋嬪簭銆?
- **娓呯悊缂撳瓨**锛氬垹闄?`Hitran_Data/*.data|*.header` 鍗冲彲锛岄渶瑕佹椂鑷姩閲嶆姄銆?
- **鎴潰搴撳垎瀛愶紙濡備笝鐑?C鈧僅鈧堬級鏌ヤ笉鍒?*锛氳鍒嗗瓙灞炴埅闈㈠簱锛屼笌閫愮嚎搴撳垎寮€鍒嗗彂銆傜敤 `hitran_xsc_molecules` 妫€绱?鈫?`hitran_xsc_files` 鍒楁竻鍗?鈫?`hitran_xsc_download` 涓€閿笅杞斤紝鍐嶇敤 `hitran_cross_section` 璇诲叆锛涙棤 API key 鏃跺彲鎸塠鍙屽簱妗ユ帴](#鍙屽簱妗ユ帴)娴佺▼鎵嬪姩涓嬭浇銆?
- **exe 琚潃杞鎶?*锛歅yInstaller 鎵撳寘鐨?Python 绋嬪簭鍋舵湁璇姤锛屽彲娣诲姞淇′换鎴栦粠婧愮爜杩愯銆?
- **鍒楁埅闈㈡竻鍗曟姤 HTTP 500 / "鏌ヨ澶辫触"**锛氳繖鏄畼鏂?`/api/v2/` 鎺ュ彛鐨勬湇鍔＄鏁呴殰锛堝疄娴嬭鎺ュ彛瀵?*鏃犳晥 key 涓庢甯?key 閮借繑鍥?500**锛屾墍浠?500 涓嶈兘璇存槑浣犵殑 key 鏈夐棶棰橈紱鍏嶇櫥褰曠殑鍦ㄧ嚎鎺㈡祴 `hitran_xsc_search` 閫氬父浠嶅彲鐢級銆傝绋嶅悗閲嶈瘯锛屾垨鍒?[hitran.org/xsc](https://hitran.org/xsc) 鐧诲綍鍚庢墜鍔ㄤ笅杞芥埅闈㈡枃浠舵斁杩?`xsc_data/`锛屽啀鐢?`hitran_cross_section` 璇诲叆銆?

</details>

## 馃敆 鐩稿叧椤圭洰

- **[SpectroLink](https://github.com/LKF0402/spectrolink)**锛氬鎶€鏈厜璋变紶鎰熶豢鐪?MCP 鎬诲叆鍙ｏ紝瑕嗙洊 7 绫绘妧鏈紙TDLAS-DA銆乀DLAS-WMS銆丩ITES銆丆RDS銆丯DIR銆丗TIR銆丏OAS锛夛紝鎷嗘垚 6 涓嫭绔?server銆傜嫭绔嬩粨搴撱€佺嫭绔嬬淮鎶わ紱涓庢湰椤圭洰涓嶉噸鍙犫€斺€旀湰椤圭洰璐熻矗 HITRAN 鍙栨暟涓庨€愮嚎/鎴潰璁＄畻锛岄渶瑕佹煇绫讳紶鎰熸妧鏈殑绔埌绔豢鐪燂紙璋冨埗绯绘暟 m銆佽皭娉€佹娴嬮檺銆佽厰琛拌崱鏃堕棿绛夛級鏃跺彲鐩存帴鎺ュ叆銆?

## 鈿栵笍 鍏嶈矗澹版槑

鏈蒋浠舵寜"鐜扮姸"锛圓S IS锛夋彁渚涳紝浣滆€呬笉瀵逛娇鐢ㄦ湰杞欢浜х敓鐨勪换浣曠洿鎺ユ垨闂存帴鎹熷け鎵挎媴璐ｄ换銆?

- 鏈蒋浠朵粎渚涚鐮斻€佹暀鑲插拰瀛︿範鐢ㄩ€旓紝涓嶆瀯鎴愪换浣曚笓涓氬缓璁垨浜у搧鎵胯銆?
- 鏈」鐩笌 macOS 搴旂敤 `HitranLab` 鍙婂叾寮€鍙戣€呫€佷笌 HITRAN 瀹樻柟鏁版嵁搴撳強鍏跺洟闃熷潎鏃犲叧鑱旓紝涔熸湭鑾峰叾鎺堟潈鎴栬儗涔︺€?
- 鍏夎氨璁＄畻缁撴灉鍩轰簬 HITRAN 鏁版嵁搴撳拰 HAPI 搴擄紝鍙兘瀛樺湪鏁版嵁鏇存柊寤惰繜銆佽绠楄繎浼兼垨璇樊銆?
- 鐢ㄦ埛搴旇嚜琛岄獙璇佽绠楃粨鏋滅殑鍑嗙‘鎬э紝鍏抽敭搴旂敤鍦烘櫙璇蜂互瀹樻柟鏁版嵁鍜屼笓涓氳蒋浠朵负鍑嗐€?
- 浣滆€呬笉淇濊瘉杞欢鏃犵己闄枫€佷笉涓柇鎴栨弧瓒崇壒瀹氶渶姹傘€?
- 浣跨敤鏈蒋浠跺嵆琛ㄧず鎮ㄥ悓鎰忚嚜琛屾壙鎷呬娇鐢ㄩ闄┿€?

## 馃搫 璁稿彲璇?

鏈」鐩噰鐢?**GPLv3** 璁稿彲璇侊紝璇﹁ [LICENSE](LICENSE)銆?

## 馃摎 References

- https://github.com/hitranonline/hapi
- https://github.com/hitranonline/hapi2
- https://github.com/hitranonline/hapiest
- https://hitran.org

