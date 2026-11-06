@echo off
REM Mo mot cua so Chrome rieng, co cong debug 9222, de scraper ket noi vao.
REM Chrome 136+ khong cho bat cong debug tren profile mac dinh, nen dung profile rieng: chrome_debug_profile.
REM Luu y: khi cua so nay mo, bat ky chuong trinh nao tren may cung dieu khien duoc no qua cong 9222.
REM Khong dang nhap tai khoan quan trong trong cua so nay, va dong no khi xong viec.

set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo Khong tim thay chrome.exe. Sua duong dan CHROME trong file nay.
  pause
  exit /b 1
)

start "" "%CHROME%" --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="%~dp0chrome_debug_profile" "https://www.panhomestores.com/uae_en/"
echo Da mo Chrome debug tren cong 9222. Vao Pan Home, bam qua buoc xac minh neu co, roi chay:
echo     python main.py scrape --only "Planter" --max-pages 2
