# KT Add-ons for HAOS --sson fork
 
HAKorea Addon 및 일부 Addon을 개인 환경(Ezville)에 맞춰 수정 중


### EzVille 월패드 RS485 Add-on

n-andFlash님이 만든 SDS월패드 애드온을 EzVille 용으로 수정. 현재 조명 및 난방 제어만 지원
MQTT discovery를 이용, 장치별로 yaml 파일을 직접 작성하지 않아도 집에 있는 모든 장치가 HA에 자동으로 추가됩니다.

### MQTT 기반 Simple EzVille Wallpad Control

MQTT only/MQTT(상태 조회) + Socket(명령)/Socket only 모드를 지원하는 Ezville Wallpad용 제어기.
MQTT Discovery로 장치를 동작 중 자동 추가합니다.

