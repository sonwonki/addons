# MQTT 기반 Simple EzVille Wallpad Control

## 1. 지원 기능

  - 조명, 난방 (외출 모드), 대기전력차단, 엘리베이터콜 상태 조회 및 제어 지원
  - 대기전력소모, 현관 스위치 상태 (외출 모드, 그룹 조명) 센서 지원
  - MQTT 기반 장치 자동 Discovery 지원

## 2. 설치 방법

  - 애드온 스토어 -> 저장소 -> [https://github.com/ktdo79/addons](https://github.com/ktdo79/addons) 추가하기 
  - MQTT 기반 Simple EzVille Wallpad Control 설치

> 사전에 MQTT Integration 및 Mosquitto Broker Addon 설치 필수

## 3. 설정 방법

### 3.1. EW11 설정

#### 3.1.1. Serial Port 설정

  - Buffer Size를 128로 변경 

#### 3.1.2. Communication Settings 설정

##### 3.1.2.1. MQTT 설정

  - +Add를 누르고 MQTT 추가 
  - Server 주소 = Home Assistant IP 주소, Port는 Mosquitto Broker 설정 Port, Buffer Size는 128 로 설정
  - Subscribe Topic는 ew11/send, Publish Topic은 ew11/recv 로 설정
  - Mosquitto Broker에 ID/Password가 있으면 MQTT Account, Password에 기입

##### 3.1.2.2. netp 설정

  - Buffer Size를 128로 변경

### 3.2. 애드온 설정

  - DEBUG (체크 박스 O/X): Debug 모드 로그
  - MQTT_LOG (체크 박스 O/X): MQTT 연결 관련 로그
  - EW11_LOG (체크 박스 O/X): EW11 연결 관련 로그
  - mode (mqtt/socket/mixed): mqtt이면 MQTT만 사용, socket이면 socket 통신만 사용, mixed면 상태 입력은 MQTT로 + 명령은 socket 사용
  - ew11_server: EW11 IP 주소
  - ew11_port: EW11 포트 (기본값 8899)
  - ew11_id: EW11 ID (EW11 리셋시 사용)
  - ew11_password: EW11 Password (EW11 리셋시 사용)
  - command_interval (초): 명령이 안 먹히는 경우 다음 명령 시도할 interval 시간 (기본값 0.5초)
  - command_retry_count (횟수): 명령이 안 먹히는 경우 최대 재시도 횟수 (기본값 20회)
  - random_backoff (체크 박스 O/X): 명령 재시도 시 jitter 방법 사용 여부 (0초 ~ command_interval초에서 random 설정)
  - discovery_delay (초): MQTT Discovery로 장치 등록 후 대기 시간 (기본값 0.1초)
  - state_loop_delay (초): State 조회 실시 간격. 짧을 수록 상태 업데이트가 빠르나 CPU 사용율 상승 (기본값 0.02초)   
  - command_loop_delay (초): HA에서 전달된 새로운 명령을 조회하는 간격. 짧을 수록 빠른 실행이 예상되나 CPU 사용율 상승 (기본값 0.02초)
  - serial_recv_dealy (초): socket mode 사용시 state를 읽어오는 간격. 짧을 수록 상태 업데이트가 빠르나 CPU 사용율 상승 (기본값 0.02초)
  - force_update_mode (체크 박스 O/X): 상태가 기존과 같으면 업데이트 하지 않으나 체크시 force_update_period마다 강제 상태 갱신 실시
  - force_update_period (초): 강제 상태 업데이트 실행 주기 (기본값 10분)
  - force_update_duration (초): 강제 상태 업데이트 실행 기간 (기본값 2초)
  - ew11_buffer_size (bytes): serial mode에서 데이터를 읽어오는 buffer size (기본값 128)
  - ew11_timeout (초): EW11이 설정 시간 이상 데이터를 읽어오지 않으면 강제 리셋 실시 (기본값 1시간)
