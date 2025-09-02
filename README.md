Auto-Approve (PyAutoGUI + OpenCV)

개요
- 화면에서 템플릿 이미지(기본: approve.png)를 찾아 버튼을 자동 클릭합니다.
- 전역 단축키로 시작/일시정지 전환(CTRL+ALT+A), 종료(CTRL+ALT+Q)가 가능합니다.
- 활성 창 제목 필터, 화면 영역 제한 등으로 동작 범위를 좁힐 수 있습니다.

중요: approve.png 교체하기
- 반드시 여러분 환경의 ‘승인(Approve)’ 버튼을 직접 캡처하여 approve.png로 교체하세요.
- 작은 크기, 높은 선명도, 여백 최소화가 핵심입니다. 실제 사용할 해상도/배율과 동일 조건에서 캡처하세요.
- Windows 캡처 팁: Win+Shift+S → 버튼만 아주 촘촘하게 드래그하여 저장 → 파일명을 approve.png로 지정해 이 폴더에 넣기

설치(Windows/PowerShell)
1) 가상환경 생성 및 의존성 설치
   python -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1
   pip install -r requirements.txt

2) 위의 지침대로 버튼을 캡처해 approve.png로 저장해 이 폴더에 둡니다.

실행
   python auto_approve.py

동작 요약
- 탐지되면: 현재 마우스 위치 저장 → (선택) 클릭 전 지연 → 중앙 클릭 → 0.5초 대기 → 원래 위치로 마우스 복귀
- 탐지 없음: 10분(기본) 동안 아무 탐지가 없으면 자동 종료

유용한 옵션(괄호는 기본값)
- 이미지 경로:         --image approve.png
- 신뢰도(0~1):         --confidence 0.85   (OpenCV 필요)
- 검색 주기(초):       --interval 0.2
- 클릭 전 지연(초):    --pre-click-delay 0.0
- 클릭 후 대기(초):    --after-click 0.5
- 검색 영역:           --region "left,top,width,height"
- 창 제목 필터:        --window-title "Your App Name"
- 클릭 수/버튼:        --clicks 1 --button left
- 자동 정지(초):       --no-detect-timeout 600   (0이면 비활성화)
- 포인터 복귀:         기본 켬; 끄려면 --no-restore-pointer, 복귀 애니메이션은 --restore-duration 0.0
- 단축키:              --toggle-hotkey "ctrl+alt+a"  --quit-hotkey "ctrl+alt+q"
- 디버그 로그:         --debug

예시
- VS Code가 활성일 때만:
  python auto_approve.py --window-title "Visual Studio Code" --confidence 0.9

- 1920x1080 화면의 좌상단 1/4만 탐색:
  python auto_approve.py --region "0,0,960,540"

문제 해결
- "PyAutoGUI was unable to import pyscreeze / Pillow" 오류:
  - 원인: Pillow 미설치 또는 Python 버전과 호환 문제
  - 해결: 가상환경 활성화 후 `pip install pillow` 실행(요구사항에 포함). Python 3.13+는 최신 Pillow(11.x+) 권장
- 전역 단축키가 동작하지 않음: Windows는 관리자 권한 PowerShell에서 실행이 필요할 수 있습니다.
- PyAutoGUI 안전장치(FAILSAFE): 마우스를 화면 좌측 상단 모서리로 이동하면 즉시 중지(예외 발생)
- 고해상도/고배율에서 인식률 저하: 캡처/실행 시 해상도와 배율을 동일하게 유지하거나 동일 조건에서 템플릿을 다시 캡처하세요.

안전/주의사항
- --window-title 또는 --region으로 동작 범위를 제한해 오클릭을 최소화하세요.
- 승인/결제 등 보안·금전적 영향이 있는 작업 자동화 시 각별히 주의하세요.

웹 환경에만 해당한다면
- 이미지 탐지 대신 DOM 셀렉터가 더 안정적일 수 있습니다(예: Tampermonkey 사용자 스크립트로 버튼 텍스트가 "Approve"인 요소 클릭).
