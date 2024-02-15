# first written by nandflash("저장장치") <github@printk.info> since 2020-06-25

import socket
import serial
import paho.mqtt.client as paho_mqtt
import json

import sys
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import os.path
import re

####################
# VIRTUAL_DEVICE = {
#    # 현관스위치: 엘리베이터 호출, 가스밸브 잠금 지원
#    "entrance": {
#        "header0": 0xAD,
#        "resp_size": 4,
#        "default": {
#            "init":  { "header1": 0x5A, "resp": 0xB05A006A, }, # 처음 전기가 들어왔거나 한동안 응답을 안했을 때, 이것부터 해야 함
#            "query": { "header1": 0x41, "resp": 0xB0560066, }, # 여기에 0xB0410071로 응답하면 gas valve 상태는 전달받지 않음
#            "gas":   { "header1": 0x56, "resp": 0xB0410071, }, # 0xAD41에 항상 0xB041로 응답하면 이게 실행될 일은 없음
#            "light": { "header1": 0x52, "resp": 0xB0520163, },
#
#            # 성공 시 ack들, 무시해도 상관 없지만...
#            "gasa":  { "header1": 0x55, "resp": 0xB0410071, },
#            "eva":   { "header1": 0x2F, "resp": 0xB0410071, },
#        },
#
#        # 0xAD41에 다르게 응답하는 방법들, 이 경우 월패드가 다시 ack를 보내준다
#        "trigger": {
#            "gas":   { "ack": 0x55, "ON": 0xB0550164, "next": None, },
#            "ev":    { "ack": 0x2F, "ON": 0xB02F011E, "next": None, },
#        },
#    },
#
#    # 신형 현관스위치
#    "entrance2": {
#        "header0": 0xCC,
#        "resp_size": 5,
#        "default": {
#            "init":  { "header1": 0x5A, "resp": 0xB05A01006B, }, # 처음 전기가 들어왔거나 한동안 응답을 안했을 때, 이것부터 해야 함
#            "query": { "header1": 0x41, "resp": 0xB041010070, }, # keepalive
#            "date":  { "header1": 0x01, "resp": 0xB001010030, }, # 스위치로 현재 날짜, 시각 전달
#            "broad": { "header1": 0x0B, "resp": 0xB00B01003A, }, # 다른 기기 상태 전달받음
#            "ukn12": { "header1": 0x12, "resp": 0xB041010070, }, # 엘리베이터 호출 결과?
#            "ukn09": { "header1": 0x09, "resp": 0xB009010038, },
#            "ukn07": { "header1": 0x07, "resp": 0xB007010137, },
#            "ukn02": { "header1": 0x02, "resp": 0xB041010070, },
#
#            # 성공 시 ack들, 무시해도 상관 없...으려나?
#            "eva":   { "header1": 0x10, "resp": 0xB041010070, },
#        },
#
#        # 0xCC41에 다르게 응답하는 방법들, 이 경우 월패드가 다시 ack를 보내준다
#        "trigger": {
#            "ev":    { "ack": 0x10, "ON": 0xB010010120, "next": None, },
#        },
#    },
#
#    # 인터폰: 공동현관 문열림 기능 지원
#    "intercom": {
#        "header0": 0xA4,
#        "resp_size": 4,
#        "default": {
#            "init":    { "header1": 0x5A, "resp": 0xB05A006A, }, # 처음 전기가 들어왔거나 한동안 응답을 안했을 때, 이것부터 해야 함
#            "query":   { "header1": 0x41, "resp": 0xB0410071, }, # 평상시
#            "block":   { "header1": 0x42, "resp": 0xB0410071, }, # 다른 인터폰이 통화중이라던지 해서 조작 거부중인 상태
#            "public":  { "header1": 0x32, "resp": 0xB0320002, }, # 공동현관 초인종 눌림
#            "private": { "header1": 0x31, "resp": 0xB0310001, }, # 현관 초인종 눌림
#            "opena":   { "header1": 0x36, "resp": 0xB0420072, }, # 통화 시작 요청 성공, 통화중이라고 ack 보내기
#            "vopena":  { "header1": 0x38, "resp": 0xB0420072, }, # 영상통화 시작 요청 성공, 통화중이라고 ack 보내기
#            "vconna":  { "header1": 0x35, "resp": 0xB0350005, }, # 영상 전송 시작됨
#            "open2a":  { "header1": 0x3B, "resp": 0xB0420072, }, # 문열림 요청 성공, 통화중이라고 ack 보내기
#            "end":     { "header1": 0x3E, "resp": 0xB03EFFFF, }, # 상황 종료, Byte[2] 가 반드시 일치해야 함
#        },
#
#        "trigger": {
#            "public":  { "ack": 0x36, "ON": 0xB0360204, "next": ("public2", "ON"), }, # 통화 시작
#            "public2": { "ack": 0x3B, "ON": 0xB03B010A, "next": ("end", "ON"), }, # 문열림
#            "priv_a":  { "ack": 0x36, "ON": 0xB0360107, "next": ("privat2", "ON"), }, # 현관 통화 시작 (초인종 울렸을 때)
#            "priv_b":  { "ack": 0x35, "ON": 0xB0380008, "next": ("privat2", "ON"), }, # 현관 통화 시작 (평상시)
#            "private": { "ack": 0x35, "ON": 0xB0380008, "next": ("privat2", "ON"), }, # 현관 통화 시작 (평상시)
#            "privat2": { "ack": 0x3B, "ON": 0xB03B000B, "next": ("end", "ON"), }, # 현관 문열림
#            "end":     { "ack": 0x3E, "ON": 0xB0420072, "next": None, }, # 문열림 후, 통화 종료 알려줄때까지 통화상태로 유지
#        },
#    },
# }

####################
# 기존 월패드 애드온의 역할하는 부분
RS485_DEVICE = {
    # 전등 스위치
    "light": {
        "query": {
            "id": 0x0E,
            "cmd": 0x01,
        },
        "state": {
            "id": 0x0E,
            "cmd": 0x81,
        },
        "last": {},
        "power": {
            "id": 0x0E,
            "cmd": 0x41,
            "ack": 0xC1,
        },
    },
    # 각방 난방 제어
    "thermostat": {
        "query": {
            "id": 0x36,
            "cmd": 0x01,
        },
        "state": {
            "id": 0x36,
            "cmd": 0x81,
        },
        "last": {},
        "away": {
            "id": 0x36,
            "cmd": 0x45,
            "ack": 0x00,
        },
        "target": {
            "id": 0x36,
            "cmd": 0x44,
            "ack": 0xC4,
        },
    },
    # KTDO: 기존 코드
    #        "query":    { "header": 0xAC79, "length":  5, "id": 2, },
    #        "state":    { "header": 0xB079, "length":  5, "id": 2, "parse": {("power", 3, "bitmap")} },
    #        "last":     { },
    #
    #        "power":    { "header": 0xAC7A, "length":  5, "id": 2, "pos": 3, },
    #    },
    #
    #    # 환기장치 (전열교환기)
    #    "fan": {
    #        "query":    { "header": 0xC24E, "length":  6, },
    #        "state":    { "header": 0xB04E, "length":  6, "parse": {("power", 4, "fan_toggle"), ("speed", 2, "value")} },
    #        "last":     { },
    #
    #        "power":    { "header": 0xC24F, "length":  6, "pos": 2, },
    #        "speed":    { "header": 0xC24F, "length":  6, "pos": 2, },
    #    },
    #
    #    # 각방 난방 제어
    #    "thermostat": {
    #        "query":    { "header": 0xAE7C, "length":  8, "id": 2, },
    #        "state":    { "header": 0xB07C, "length":  8, "id": 2, "parse": {("power", 3, "heat_toggle"), ("target", 4, "value"), ("current", 5, "value")} },
    #        "last":     { },
    #
    #        "power":    { "header": 0xAE7D, "length":  8, "id": 2, "pos": 3, },
    #        "target":   { "header": 0xAE7F, "length":  8, "id": 2, "pos": 3, },
    #    },
    #
    #    # 각방 난방 제어
    #    "thermostat": {
    #        "query":    { "header": 0xAE7C, "length":  8, "id": 2, },
    #        "state":    { "header": 0xB07C, "length":  8, "id": 2, "parse": {("power", 3, "heat_toggle"), ("target", 4, "value"), ("current", 5, "value")} },
    #        "last":     { },
    #
    #        "power":    { "header": 0xAE7D, "length":  8, "id": 2, "pos": 3, },
    #        "target":   { "header": 0xAE7F, "length":  8, "id": 2, "pos": 3, },
    #    },
    #
    #    # 대기전력차단 스위치 (전력사용량 확인)
    #    "plug": {
    #        "query":    { "header": 0xC64A, "length": 10, "id": 2, },
    #        "state":    { "header": 0xB04A, "length": 10, "id": 2, "parse": {("power", 3, "toggle"), ("idlecut", 3, "toggle2"), ("current", 5, "2Byte")} },
    #        "last":     { },
    #
    #        "power":    { "header": 0xC66E, "length": 10, "id": 2, "pos": 3, },
    #        "idlecut":  { "header": 0xC64B, "length": 10, "id": 2, "pos": 3, },
    #    },
    #
    #    # 일괄조명: 현관 스위치 살아있으면...
    #    "cutoff": {
    #        "query":    { "header": 0xAD52, "length":  4, },
    #        "state":    { "header": 0xB052, "length":  4, "parse": {("power", 2, "toggle")} }, # 1: 정상, 0: 일괄소등
    #        "last":     { },
    #
    #        "power":    { "header": 0xAD53, "length":  4, "pos": 2, },
    #    },
    #
    #    # 부엌 가스 밸브
    #    "gas_valve": {
    #        "query":    { "header": 0xAB41, "length":  4, },
    #        #"state":    { "header": 0xB041, "length":  4, "parse": {("power", 2, "toggle")} }, # 0: 정상, 1: 차단; 0xB041은 공용 ack이므로 처리하기 복잡함
    #        "state":    { "header": 0xAD56, "length":  4, "parse": {("power", 2, "gas_toggle")} }, # 0: 정상, 1: 차단; 월패드가 현관 스위치에 보내주는 정보로 확인 가능
    #        "last":     { },
    #
    #        "power":    { "header": 0xAB78, "length":  4, }, # 0 으로 잠그기만 가능
    #    },
    #
    #    # 실시간에너지 0:전기, 1:가스, 2:수도
    #    "energy": {
    #        "query":    { "header": 0xAA6F, "length":  4, "id": 2, },
    #        "state":    { "header": 0xB06F, "length":  7, "id": 2, "parse": {("current", 3, "6decimal")} },
    #        "last":     { },
    #    },
}

DISCOVERY_DEVICE = {
    "ids": [
        "ezville_wallpad",
    ],
    "name": "ezville_wallpad",
    "mf": "EzVille",
    "mdl": "EzVille Wallpad",
    "sw": "ktdo79/ha_addons/ezville_wallpad",
}

# DISCOVERY_VIRTUAL = {
#    "entrance": [
#        {
#            "_intg": "switch",
#            "~": "{}/virtual/entrance/ev",
#            "name": "{}_elevator",
#            "stat_t": "~/state",
#            "cmd_t": "~/command",
#            "icon": "mdi:elevator",
#        },
#        {
#            "_intg": "switch",
#            "~": "{}/virtual/entrance/gas",
#            "name": "{}_gas_cutoff",
#            "stat_t": "~/state",
#            "cmd_t": "~/command",
#            "icon": "mdi:valve",
#        },
#    ],
#    "entrance2": [
#        {
#            "_intg": "switch",
#            "~": "{}/virtual/entrance2/ev",
#            "name": "{}_new_elevator",
#            "stat_t": "~/state",
#            "cmd_t": "~/command",
#            "icon": "mdi:elevator",
#        },
#    ],
#    "intercom": [
#        {
#            "_intg": "switch",
#            "~": "{}/virtual/intercom/public",
#            "name": "{}_intercom_public",
#            "avty_t": "~/available",
#            "stat_t": "~/state",
#            "cmd_t": "~/command",
#            "icon": "mdi:door-closed",
#        },
#        {
#            "_intg": "switch",
#            "~": "{}/virtual/intercom/private",
#            "name": "{}_intercom_private",
#            "stat_t": "~/state",
#            "cmd_t": "~/command",
#            "icon": "mdi:door-closed",
#        },
#        {
#            "_intg": "binary_sensor",
#            "~": "{}/virtual/intercom/public",
#            "name": "{}_intercom_public",
#            "dev_cla": "sound",
#            "stat_t": "~/available",
#            "pl_on": "online",
#            "pl_off": "offline",
#        },
#        {
#            "_intg": "binary_sensor",
#            "~": "{}/virtual/intercom/private",
#            "name": "{}_intercom_private",
#            "dev_cla": "sound",
#            "stat_t": "~/available",
#            "pl_on": "online",
#            "pl_off": "offline",
#        },
#    ],
# }

DISCOVERY_PAYLOAD = {
    "light": [
        {
            "_intg": "light",
            "~": "{prefix}/light/{grp}_{rm}_{id}",
            "name": "{prefix}_light_{grp}_{rm}_{id}",
            "opt": True,
            "stat_t": "~/power/state",
            "cmd_t": "~/power/command",
        }
    ],
    #   "fan": [ {
    #       "_intg": "fan",
    #       "~": "{prefix}/fan/{idn}",
    #       "name": "{prefix}_fan_{idn}",
    #       "opt": True,
    #       "stat_t": "~/power/state",
    #       "cmd_t": "~/power/command",
    #       "spd_stat_t": "~/speed/state",
    #       "spd_cmd_t": "~/speed/command",
    #       "pl_on": 5,
    #       "pl_off": 6,
    #       "pl_lo_spd": 3,
    #       "pl_med_spd": 2,
    #       "pl_hi_spd": 1,
    #       "spds": ["low", "medium", "high"],
    #   } ],
    "thermostat": [
        {
            "_intg": "climate",
            "~": "{prefix}/thermostat/{grp}_{id}",
            "name": "{prefix}_thermostat_{grp}_{id}",
            "mode_stat_t": "~/power/state",
            "temp_stat_t": "~/target/state",
            "temp_cmd_t": "~/target/command",
            "curr_temp_t": "~/current/state",
            "away_stat_t": "~/away/state",
            "away_cmd_t": "~/away/command",
            "modes": ["off", "heat"],
            "min_temp": 5,
            "max_temp": 40,
        }
    ],
    #    "plug": [ {
    #        "_intg": "switch",
    #        "~": "{prefix}/plug/{idn}/power",
    #        "name": "{prefix}_plug_{idn}",
    #        "stat_t": "~/state",
    #        "cmd_t": "~/command",
    #        "icon": "mdi:power-plug",
    #    },
    #    {
    #        "_intg": "switch",
    #        "~": "{prefix}/plug/{idn}/idlecut",
    #        "name": "{prefix}_plug_{idn}_standby_cutoff",
    #        "stat_t": "~/state",
    #        "cmd_t": "~/command",
    #        "icon": "mdi:leaf",
    #    },
    #    {
    #        "_intg": "sensor",
    #        "~": "{prefix}/plug/{idn}",
    #        "name": "{prefix}_plug_{idn}_power_usage",
    #        "stat_t": "~/current/state",
    #        "unit_of_meas": "W",
    #    } ],
    #    "cutoff": [ {
    #        "_intg": "switch",
    #        "~": "{prefix}/cutoff/{idn}/power",
    #        "name": "{prefix}_light_cutoff_{idn}",
    #        "stat_t": "~/state",
    #        "cmd_t": "~/command",
    #    } ],
    #    "gas_valve": [ {
    #        "_intg": "sensor",
    #        "~": "{prefix}/gas_valve/{idn}",
    #        "name": "{prefix}_gas_valve_{idn}",
    #        "stat_t": "~/power/state",
    #        "icon": "mdi:valve",
    #    } ],
    #    "energy": [ {
    #        "_intg": "sensor",
    #        "~": "{prefix}/energy/{idn}",
    #        "name": "_",
    #        "stat_t": "~/current/state",
    #        "unit_of_meas": "_",
    #        "val_tpl": "_",
    #    } ],
}

STATE_HEADER = {
    prop["state"]["id"]: (device, prop["state"]["cmd"])
    for device, prop in RS485_DEVICE.items()
    if "state" in prop
}
QUERY_HEADER = {
    prop["query"]["id"]: (device, prop["query"]["cmd"])
    for device, prop in RS485_DEVICE.items()
    if "query" in prop
}
# 제어 명령의 ACK header만 모음
ACK_HEADER = {
    prop[cmd]["id"]: (device, prop[cmd]["ack"])
    for device, prop in RS485_DEVICE.items()
    for cmd, code in prop.items()
    if "ack" in code
}

# KTDO: 제어 명령과 ACK의 Pair 저장
ACK_MAP = {}
for device, prop in RS485_DEVICE.items():
    for cmd, code in prop.items():
        if "ack" in code:
            ACK_MAP[code["id"]] = {}
            ACK_MAP[code["id"]][code["cmd"]] = {}
            ACK_MAP[code["id"]][code["cmd"]] = code["ack"]

# KTDO: 아래 미사용으로 코멘트 처리
# HEADER_0_STATE = 0xB0
# KTDO: Ezville에서는 가스밸브 STATE Query 코드로 처리
HEADER_0_FIRST = [[0x12, 0x01], [0x12, 0x0F]]
# KTDO: Virtual은 Skip
# header_0_virtual = {}
# KTDO: 아래 미사용으로 코멘트 처리
# HEADER_1_SCAN = 0x5A
header_0_first_candidate = [[[0x33, 0x01], [0x33, 0x0F]], [[0x36, 0x01], [0x36, 0x0F]]]


# human error를 로그로 찍기 위해서 그냥 전부 구독하자
# SUB_LIST = { "{}/{}/+/+/command".format(Options["mqtt"]["prefix"], device) for device in RS485_DEVICE } |\
#           { "{}/virtual/{}/+/command".format(Options["mqtt"]["prefix"], device) for device in VIRTUAL_DEVICE }

# KTDO: Virtual은 Skip
# virtual_watch = {}
# virtual_trigger = {}
# virtual_ack = {}
# virtual_avail = []

serial_queue = {}
serial_ack = {}

last_query = int(0).to_bytes(2, "big")
last_topic_list = {}

mqtt = paho_mqtt.Client(paho_mqtt.CallbackAPIVersion.VERSION2)
mqtt_connected = False

logger = logging.getLogger(__name__)


# KTDO: 수정 완료
class EzVilleSerial:
    def __init__(self):
        self._ser = serial.Serial()
        self._ser.port = Options["serial"]["port"]
        self._ser.baudrate = Options["serial"]["baudrate"]
        self._ser.bytesize = Options["serial"]["bytesize"]
        self._ser.parity = Options["serial"]["parity"]
        self._ser.stopbits = Options["serial"]["stopbits"]

        self._ser.close()
        self._ser.open()

        self._pending_recv = 0

        # 시리얼에 뭐가 떠다니는지 확인
        self.set_timeout(5.0)
        data = self._recv_raw(1)
        self.set_timeout(None)
        if not data:
            logger.critical("no active packet at this serial port!")

    def _recv_raw(self, count=1):
        return self._ser.read(count)

    def recv(self, count=1):
        # serial은 pending count만 업데이트
        self._pending_recv = max(self._pending_recv - count, 0)
        return self._recv_raw(count)

    def send(self, a):
        self._ser.write(a)

    def set_pending_recv(self):
        self._pending_recv = self._ser.in_waiting

    def check_pending_recv(self):
        return self._pending_recv

    def check_in_waiting(self):
        return self._ser.in_waiting

    def set_timeout(self, a):
        self._ser.timeout = a


# KTDO: 수정 완료
class EzVilleSocket:
    def __init__(self):
        addr = Options["socket"]["address"]
        port = Options["socket"]["port"]

        self._soc = socket.socket()
        self._soc.connect((addr, port))

        self._recv_buf = bytearray()
        self._pending_recv = 0

        # 소켓에 뭐가 떠다니는지 확인
        self.set_timeout(5.0)
        data = self._recv_raw(1)
        self.set_timeout(None)
        if not data:
            logger.critical("no active packet at this socket!")

    def _recv_raw(self, count=1):
        return self._soc.recv(count)

    def recv(self, count=1):
        # socket은 버퍼와 in_waiting 직접 관리
        if len(self._recv_buf) < count:
            new_data = self._recv_raw(256)
            self._recv_buf.extend(new_data)
        if len(self._recv_buf) < count:
            return None

        self._pending_recv = max(self._pending_recv - count, 0)

        res = self._recv_buf[0:count]
        del self._recv_buf[0:count]
        return res

    def send(self, a):
        self._soc.sendall(a)

    def set_pending_recv(self):
        self._pending_recv = len(self._recv_buf)

    def check_pending_recv(self):
        return self._pending_recv

    def check_in_waiting(self):
        if len(self._recv_buf) == 0:
            new_data = self._recv_raw(256)
            self._recv_buf.extend(new_data)
        return len(self._recv_buf)

    def set_timeout(self, a):
        self._soc.settimeout(a)


# KTDO: 수정 완료
def init_logger():
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# KTDO: 수정 완료
def init_logger_file():
    if Options["log"]["to_file"]:
        filename = Options["log"]["filename"]
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = TimedRotatingFileHandler(
            os.path.abspath(Options["log"]["filename"]), when="midnight", backupCount=7
        )
        handler.setFormatter(formatter)
        handler.suffix = "%Y%m%d"
        logger.addHandler(handler)


# KTDO: 수정 완료
def init_option(argv):
    # option 파일 선택
    if len(argv) == 1:
        option_file = "./options_standalone.json"
    else:
        option_file = argv[1]

    # configuration이 예전 버전이어도 최대한 동작 가능하도록,
    # 기본값에 해당하는 파일을 먼저 읽고나서 설정 파일로 업데이트 한다.
    global Options

    # 기본값 파일은 .py 와 같은 경로에 있음
    default_file = os.path.join(
        os.path.dirname(os.path.abspath(argv[0])), "config.json"
    )

    with open(default_file) as f:
        config = json.load(f)
        logger.info("addon version {}".format(config["version"]))
        Options = config["options"]
    with open(option_file) as f:
        Options2 = json.load(f)

    # 업데이트
    for k, v in Options.items():
        if type(v) is dict and k in Options2:
            Options[k].update(Options2[k])
            for k2 in Options[k].keys():
                if k2 not in Options2[k].keys():
                    logger.warning(
                        "no configuration value for '{}:{}'! try default value ({})...".format(
                            k, k2, Options[k][k2]
                        )
                    )
        else:
            if k not in Options2:
                logger.warning(
                    "no configuration value for '{}'! try default value ({})...".format(
                        k, Options[k]
                    )
                )
            else:
                Options[k] = Options2[k]

    # 관용성 확보
    Options["mqtt"]["server"] = re.sub("[a-z]*://", "", Options["mqtt"]["server"])
    if Options["mqtt"]["server"] == "127.0.0.1":
        logger.warning("MQTT server address should be changed!")

    # internal options
    Options["mqtt"]["_discovery"] = Options["mqtt"]["discovery"]


# def init_virtual_device():
#    global virtual_watch
#
#    if Options["entrance_mode"] == "full" or Options["entrance_mode"] == "new":
#        if Options["entrance_mode"] == "new":
#            ent = "entrance2"
#        else:
#            ent = "entrance"
#
#        header_0_virtual[VIRTUAL_DEVICE[ent]["header0"]] = ent
#        virtual_trigger[ent] = {}
#
#        # 평상시 응답할 항목 등록
#        virtual_watch.update({
#            (VIRTUAL_DEVICE[ent]["header0"] << 8) + prop["header1"]: prop["resp"].to_bytes(VIRTUAL_DEVICE[ent]["resp_size"], "big")
#            for prop in VIRTUAL_DEVICE[ent]["default"].values()
#        })
#
#        # full 모드에서 일괄소등 지원 안함
#        STATE_HEADER.pop(RS485_DEVICE["cutoff"]["state"]["header"])
#        RS485_DEVICE.pop("cutoff")
#
#    if Options["intercom_mode"] == "on":
#        VIRTUAL_DEVICE["intercom"]["header0"] = int(Options["rs485"]["intercom_header"][:2], 16)
#
#        header_0_virtual[VIRTUAL_DEVICE["intercom"]["header0"]] = "intercom"
#        virtual_trigger["intercom"] = {}
#
#        # 평상시 응답할 항목 등록
#        virtual_watch.update({
#            (VIRTUAL_DEVICE["intercom"]["header0"] << 8) + prop["header1"]: prop["resp"].to_bytes(4, "big")
#            for prop in VIRTUAL_DEVICE["intercom"]["default"].values()
#        })
#
#        # availability 관련
#        for header_1 in (0x31, 0x32, 0x36, 0x3E):
#            virtual_avail.append((VIRTUAL_DEVICE["intercom"]["header0"] << 8) + header_1)


# KTDO: 수정 완료
def mqtt_discovery(payload):
    intg = payload.pop("_intg")

    # MQTT 통합구성요소에 등록되기 위한 추가 내용
    payload["device"] = DISCOVERY_DEVICE
    payload["uniq_id"] = payload["name"]

    # discovery에 등록
    topic = "homeassistant/{}/ezville_wallpad/{}/config".format(intg, payload["name"])
    logger.info("Add new device:  {}".format(topic))
    mqtt.publish(topic, json.dumps(payload))


# def mqtt_add_virtual():
#    # 현관스위치 장치 등록
#    if Options["entrance_mode"] != "off":
#        if Options["entrance_mode"] == "new":
#            ent = "entrance2"
#        else:
#            ent = "entrance"
#
#        prefix = Options["mqtt"]["prefix"]
#        for payloads in DISCOVERY_VIRTUAL[ent]:
#            payload = payloads.copy()
#            payload["~"] = payload["~"].format(prefix)
#            payload["name"] = payload["name"].format(prefix)
#
#            mqtt_discovery(payload)
#
#            # 트리거 초기 상태 설정
#            topic = payload["~"] + "/state"
#            logger.info("initial state:   {} = OFF".format(topic))
#            mqtt.publish(topic, "OFF")
#
#    # 인터폰 장치 등록
#    if Options["intercom_mode"] != "off":
#        prefix = Options["mqtt"]["prefix"]
#        for payloads in DISCOVERY_VIRTUAL["intercom"]:
#            payload = payloads.copy()
#            payload["~"] = payload["~"].format(prefix)
#            payload["name"] = payload["name"].format(prefix)
#
#            mqtt_discovery(payload)
#
#            # 트리거 초기 상태 설정
#            topic = payload["~"] + "/state"
#            logger.info("initial state:   {} = OFF".format(topic))
#            mqtt.publish(topic, "OFF")
#
#        # 초인종 울리기 전까지 문열림 스위치 offline으로 설정
#        payload = "offline"
#        topic = "{}/virtual/intercom/public/available".format(prefix)
#        logger.info("doorlock state:  {} = {}".format(topic, payload))
#        mqtt.publish(topic, payload)
#        topic = "{}/virtual/intercom/private/available".format(prefix)
#        logger.info("doorlock state:  {} = {}".format(topic, payload))
#        mqtt.publish(topic, payload)


# def mqtt_virtual(topics, payload):
#    device = topics[2]
#    trigger = topics[3]
#    triggers = VIRTUAL_DEVICE[device]["trigger"]
#
#    # HA에서 잘못 보내는 경우 체크
#    if len(topics) != 5:
#        logger.error("    invalid topic length!"); return
#    if trigger not in triggers:
#        logger.error("    invalid trigger!"); return
#
#    # OFF가 없는데(ev, gas) OFF가 오면, 이전 ON 명령의 시도 중지
#    if payload not in triggers[trigger]:
#        virtual_pop(device, trigger, "ON")
#        return
#
#    # 오류 체크 끝났으면 queue 에 넣어둠
#    virtual_trigger[device][(trigger, payload)] = time.time()
#
#    # ON만 있는 명령은, 명령이 queue에 있는 동안 switch를 ON으로 표시
#    prefix = Options["mqtt"]["prefix"]
#    if "OFF" not in triggers[trigger]:
#        topic = "{}/virtual/{}/{}/state".format(prefix, device, trigger)
#        logger.info("publish to HA:   {} = {}".format(topic, "ON"))
#        mqtt.publish(topic, "ON")
#
#    # ON/OFF 있는 명령은, 마지막으로 받은 명령대로 표시
#    else:
#        topic = "{}/virtual/{}/{}/state".format(prefix, device, trigger)
#        logger.info("publish to HA:   {} = {}".format(topic, payload))
#        mqtt.publish(topic, payload)
#
#    # 그동안 조용히 있었어도, 이젠 가로채서 응답해야 함
#    if device == "entrance" and Options["entrance_mode"] == "minimal":
#        query = VIRTUAL_DEVICE["entrance"]["default"]["query"]
#        virtual_watch[query["header"]] = query["resp"]


# KTDO: 수정 완료
def mqtt_debug(topics, payload):
    device = topics[2]
    command = topics[3]

    if device == "packet":
        if command == "send":
            # parity는 여기서 재생성
            packet = bytearray.fromhex(payload)
            packet[-2], packet[-1] = serial_generate_checksum(packet)
            packet = bytes(packet)

            logger.info("prepare packet:  {}".format(packet.hex()))
            serial_queue[packet] = time.time()


# KTDO: 수정 완료
def mqtt_device(topics, payload):
    device = topics[1]
    idn = topics[2]
    cmd = topics[3]

    # HA에서 잘못 보내는 경우 체크
    if device not in RS485_DEVICE:
        logger.error("    unknown device!")
        return
    if cmd not in RS485_DEVICE[device]:
        logger.error("    unknown command!")
        return
    if payload == "":
        logger.error("    no payload!")
        return

    # ON, OFF인 경우만 1, 0으로 변환, 복잡한 경우 (fan 등) 는 값으로 받자
    if payload == "ON":
        payload = "1"
    elif payload == "OFF":
        payload = "0"
    elif payload == "heat":
        payload = "1"
    elif payload == "off":
        payload = "0"

    # 오류 체크 끝났으면 serial 메시지 생성
    cmd = RS485_DEVICE[device][cmd]

    if device == "light":
        length = 10
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x03
        packet[5] = int(idn.split("_")[2])
        packet[6] = int(float(payload))
        packet[7] = 0x00
        packet[8], packet[9] = serial_generate_checksum(packet)

    elif device == "thermostat":
        length = 8
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x01
        packet[5] = int(float(payload))
        packet[6], packet[7] = serial_generate_checksum(packet)

    packet = bytes(packet)

    # KTDO: 상기 코드로 대체
    # packet = bytearray(cmd["length"])
    # packet[0] = cmd["header"] >> 8
    # packet[1] = cmd["header"] & 0xFF
    # packet[cmd["pos"]] = int(float(payload))
    #
    # if "id" in cmd: packet[cmd["id"]] = int(idn)
    #
    ## parity 생성 후 queue 에 넣어둠
    # packet[-1] = serial_generate_checksum(packet)
    # packet = bytes(packet)

    serial_queue[packet] = time.time()


# KTDO: 수정 완료
def mqtt_init_discovery():
    # HA가 재시작됐을 때 모든 discovery를 다시 수행한다
    Options["mqtt"]["_discovery"] = Options["mqtt"]["discovery"]
    # KTDO: Virtual Device는 Skip
    #    mqtt_add_virtual()
    for device in RS485_DEVICE:
        RS485_DEVICE[device]["last"] = {}

    global last_topic_list
    last_topic_list = {}


# KTDO: 수정 완료
def mqtt_on_message(mqtt, userdata, msg):
    topics = msg.topic.split("/")
    payload = msg.payload.decode()

    logger.info("recv. from HA:   {} = {}".format(msg.topic, payload))

    device = topics[1]
    if device == "status":
        if payload == "online":
            mqtt_init_discovery()
    # KTDO: Virtual Device는 Skip
    #    elif device == "virtual":
    #        mqtt_virtual(topics, payload)
    elif device == "debug":
        mqtt_debug(topics, payload)
    else:
        mqtt_device(topics, payload)


# KTDO: 수정 완료
def mqtt_on_connect(mqtt, userdata, flags, rc, properties):
    if rc == 0:
        logger.info("MQTT connect successful!")
        global mqtt_connected
        mqtt_connected = True
    else:
        logger.error(
            "MQTT connection return with:  {}".format(paho_mqtt.connack_string(rc))
        )

    mqtt_init_discovery()

    topic = "homeassistant/status"
    logger.info("subscribe {}".format(topic))
    mqtt.subscribe(topic, 0)

    prefix = Options["mqtt"]["prefix"]
    # KTDO: Virtual 관련 일단 comment
    #    if Options["entrance_mode"] != "off" or Options["intercom_mode"] != "off":
    #        topic = "{}/virtual/+/+/command".format(prefix)
    #        logger.info("subscribe {}".format(topic))
    #        mqtt.subscribe(topic, 0)
    if Options["wallpad_mode"] != "off":
        topic = "{}/+/+/+/command".format(prefix)
        logger.info("subscribe {}".format(topic))
        mqtt.subscribe(topic, 0)


# KTDO: 수정 완료
def mqtt_on_disconnect(mqtt, userdata, rc):
    logger.warning("MQTT disconnected! ({})".format(rc))
    global mqtt_connected
    mqtt_connected = False


# KTDO: 수정 완료
def start_mqtt_loop():
    logger.info("initialize mqtt...")

    mqtt.on_message = mqtt_on_message
    mqtt.on_connect = mqtt_on_connect
    mqtt.on_disconnect = mqtt_on_disconnect

    if Options["mqtt"]["need_login"]:
        mqtt.username_pw_set(Options["mqtt"]["user"], Options["mqtt"]["passwd"])

    try:
        mqtt.connect(Options["mqtt"]["server"], Options["mqtt"]["port"])
    except Exception as e:
        logger.error("MQTT server address/port may be incorrect! ({})".format(str(e)))
        sys.exit(1)

    mqtt.loop_start()

    delay = 1
    while not mqtt_connected:
        logger.info("waiting MQTT connected ...")
        time.sleep(delay)
        delay = min(delay * 2, 10)


# def virtual_enable(header_0, header_1):
#    prefix = Options["mqtt"]["prefix"]
#
#    # 마무리만 하드코딩으로 좀 하자... 슬슬 귀찮다
#    if header_1 == 0x32:
#        payload = "online"
#        topic = "{}/virtual/intercom/public/available".format(prefix)
#        logger.info("doorlock status: {} = {}".format(topic, payload))
#        mqtt.publish(topic, payload)
#
#    elif header_1 == 0x31:
#        payload = "online"
#        topic = "{}/virtual/intercom/private/available".format(prefix)
#        logger.info("doorlock status: {} = {}".format(topic, payload))
#        mqtt.publish(topic, payload)
#        VIRTUAL_DEVICE["intercom"]["trigger"]["private"] = VIRTUAL_DEVICE["intercom"]["trigger"]["priv_a"]
#
#    elif header_1 == 0x36 or header_1 == 0x3E:
#        payload = "offline"
#        topic = "{}/virtual/intercom/public/available".format(prefix)
#        logger.info("doorlock status: {} = {}".format(topic, payload))
#        mqtt.publish(topic, payload)
#        topic = "{}/virtual/intercom/private/available".format(prefix)
#        logger.info("doorlock status: {} = {}".format(topic, payload))
#        mqtt.publish(topic, payload)
#        VIRTUAL_DEVICE["intercom"]["trigger"]["private"] = VIRTUAL_DEVICE["intercom"]["trigger"]["priv_b"]


# def virtual_pop(device, trigger, cmd):
#    query = VIRTUAL_DEVICE[device]["default"]["query"]
#    triggers = VIRTUAL_DEVICE[device]["trigger"]
#
#    virtual_trigger[device].pop((trigger, cmd), None)
#    virtual_ack.pop((VIRTUAL_DEVICE[device]["header0"] << 8) + triggers[trigger]["ack"], None)
#
#    # 명령이 queue에서 빠지면 OFF로 표시
#    prefix = Options["mqtt"]["prefix"]
#    topic = "{}/virtual/{}/{}/state".format(prefix, device, trigger)
#    logger.info("publish to HA:   {} = {}".format(topic, "OFF"))
#    mqtt.publish(topic, "OFF")
#
#    # minimal 모드일 때, 조용해질지 여부
#    if not virtual_trigger[device] and Options["entrance_mode"] == "minimal":
#        entrance_watch.pop(query["header"], None)


# def virtual_query(header_0, header_1):
#    device = header_0_virtual[header_0]
#    query = VIRTUAL_DEVICE[device]["default"]["query"]["header1"]
#    triggers = VIRTUAL_DEVICE[device]["trigger"]
#    resp_size = VIRTUAL_DEVICE[device]["resp_size"]
#
#    # pending이 남은 상태면 지금 시도해봐야 가망이 없음
#    if conn.check_pending_recv():
#        return
#
#    # 아직 2Byte 덜 받았으므로 올때까지 기다리는게 정석 같지만,
#    # 조금 일찍 시작하는게 성공률이 더 높은거 같기도 하다.
#    length = 2 - Options["rs485"]["early_response"]
#    if length > 0:
#        while conn.check_in_waiting() < length: pass
#
#    if virtual_trigger[device] and header_1 == query:
#        # 하나 뽑아서 보내봄
#        trigger, cmd = next(iter(virtual_trigger[device]))
#        resp = triggers[trigger][cmd].to_bytes(resp_size, "big")
#        conn.send(resp)
#
#        # retry time 관리, 초과했으면 제거
#        elapsed = time.time() - virtual_trigger[device][trigger, cmd]
#        if elapsed > Options["rs485"]["max_retry"]:
#            logger.error("send to wallpad: {} max retry time exceeded!".format(resp.hex()))
#            virtual_pop(device, trigger, cmd)
#        elif elapsed > 3:
#            logger.warning("send to wallpad: {}, try another {:.01f} seconds...".format(resp.hex(), Options["rs485"]["max_retry"] - elapsed))
#            virtual_ack[(header_0 << 8) + triggers[trigger]["ack"]] = (device, trigger, cmd)
#        else:
#            logger.info("send to wallpad: {}".format(resp.hex()))
#            virtual_ack[(header_0 << 8) + triggers[trigger]["ack"]] = (device, trigger, cmd)
#
#    # full 모드일 때, 일상 응답
#    else:
#        header = (header_0 << 8) | header_1
#        if header in virtual_watch:
#            resp = virtual_watch[header]
#
#            # Byte[2] 가 wallpad를 따라가야 하는 경우
#            if resp[2] == 0xFF:
#                ba = bytearray(resp)
#                ba[2] = conn.recv(1)[0]
#                ba[3] = serial_generate_checksum(ba)
#                resp = bytes(ba)
#
#            conn.send(resp)


# def virtual_clear(header):
#    logger.info("ack frm wallpad: {}".format(hex(header)))
#
#    device, trigger, cmd = virtual_ack[header]
#    triggers = VIRTUAL_DEVICE[device]["trigger"]
#
#    # 성공한 명령을 지움
#    virtual_pop(*virtual_ack[header])
#    virtual_ack.pop(header, None)
#
#    # 다음 트리거로 이어지면 추가
#    if triggers[trigger]["next"] != None:
#        next_trigger = triggers[trigger]["next"]
#        virtual_trigger[device][next_trigger] = time.time()


# KTDO: 수정 완료
def serial_verify_checksum(packet):
    # 모든 byte를 XOR
    # KTDO: 마지막 ADD 빼고 XOR
    checksum = 0
    for b in packet[:-1]:
        checksum ^= b

    # KTDO: ADD 계산
    add = sum(packet[:-1]) & 0xFF

    # parity의 최상위 bit는 항상 0
    # KTDO: EzVille은 아님
    # if checksum >= 0x80: checksum -= 0x80

    # checksum이 안맞으면 로그만 찍고 무시
    # KTDO: ADD 까지 맞아야함.
    if checksum or add != packet[-1]:
        logger.warning(
            "checksum fail! {}, {:02x}, {:02x}".format(packet.hex(), checksum, add)
        )
        return False

    # 정상
    return True


# KTDO: 수정 완료
def serial_generate_checksum(packet):
    # 마지막 제외하고 모든 byte를 XOR
    checksum = 0
    for b in packet[:-1]:
        checksum ^= b

    # KTDO: add 추가 생성
    add = (sum(packet) + checksum) & 0xFF

    # KTDO: EzVille은 그냥 XOR
    #    # parity의 최상위 bit는 항상 0
    #    if checksum >= 0x80: checksum -= 0x80
    #    checksumadd = (checksum << 8) | add

    #    return checksumadd
    return checksum, add


# KTDO: 코멘트 처리
# def serial_peek_value(device, packet):
#    attr, pos, pattern = parse
#    value = packet[pos]
#
#    if device == "light":
#        res = []
#        for i in range(1, 8+1):
#            res += [("{}{}".format(attr, i), "ON" if value & 1 else "OFF")]
#            value >>= 1
#        return res
#    elif pattern == "toggle":
#        value = "ON" if value & 1 else "OFF"
#    elif pattern == "toggle2":
#        value = "ON" if value & 0x10 else "OFF"
#    elif pattern == "fan_toggle":
#        value = 5 if value == 0 else 6
#    elif pattern == "heat_toggle":
#        value = "heat" if value & 1 else "off"
#    elif pattern == "gas_toggle":
#        value = "차단" if value & 1 else "열림"
#    elif pattern == "value":
#        pass
#    elif pattern == "2Byte":
#        value += packet[pos-1] << 8
#    elif pattern == "6decimal":
#        try:
#            value = packet[pos : pos+3].hex()
#        except:
#            # 어쩌다 깨지면 뻗음...
#            logger.warning("invalid packet, {} is not decimal".format(packet.hex()))
#            value = 0
#
#    return [(attr, value)]


# KTDO: 수정 완료
def serial_new_device(device, packet):
    prefix = Options["mqtt"]["prefix"]

    # 조명은 두 id를 조합해서 개수와 번호를 정해야 함
    if device == "light":
        # KTDO: EzVille에 맞게 수정
        grp_id = int(packet[2] >> 4)
        rm_id = int(packet[2] & 0x0F)
        light_count = int(packet[4]) - 1

        # id2 = last_query[3]
        # num = idn >> 4
        # idn = int("{:x}".format(idn))

        for id in range(1, light_count + 1):
            payload = DISCOVERY_PAYLOAD[device][0].copy()
            payload["~"] = payload["~"].format(
                prefix=prefix, grp=grp_id, rm=rm_id, id=id
            )
            payload["name"] = payload["name"].format(
                prefix=prefix, grp=grp_id, rm=rm_id, id=id
            )

            mqtt_discovery(payload)

    elif device == "thermostat":
        # KTDO: EzVille에 맞게 수정
        grp_id = int(packet[2] >> 4)
        room_count = int((int(packet[4]) - 5) / 2)

        for id in range(1, room_count + 1):
            payload = DISCOVERY_PAYLOAD[device][0].copy()
            payload["~"] = payload["~"].format(prefix=prefix, grp=grp_id, id=id)
            payload["name"] = payload["name"].format(prefix=prefix, grp=grp_id, id=id)

            mqtt_discovery(payload)


#    elif device in DISCOVERY_PAYLOAD:
#        for payloads in DISCOVERY_PAYLOAD[device]:
#            payload = payloads.copy()
#            payload["~"] = payload["~"].format(prefix=prefix, idn=idn)
#            payload["name"] = payload["name"].format(prefix=prefix, idn=idn)
#
#            # 실시간 에너지 사용량에는 적절한 이름과 단위를 붙여준다 (단위가 없으면 그래프로 출력이 안됨)
#            # KTDO: Ezville에 에너지 확인 쿼리 없음
#            if device == "energy":
#                payload["name"] = "{}_{}_consumption".format(prefix, ("power", "gas", "water")[idn])
#                payload["unit_of_meas"] = ("W", "m³/h", "m³/h")[idn]
#                payload["val_tpl"] = ("{{ value }}", "{{ value | float / 100 }}", "{{ value | float / 100 }}")[idn]
#
#            mqtt_discovery(payload)


# KTDO: 수정 완료
def serial_receive_state(device, packet):
    form = RS485_DEVICE[device]["state"]
    last = RS485_DEVICE[device]["last"]

    # if form.get("id") != None:
    #    idn = packet[form["id"]]
    # else:
    #    idn = 1
    idn = (packet[1] << 8) | packet[2]

    # 해당 ID의 이전 상태와 같은 경우 바로 무시
    if last.get(idn) == packet:
        return

    # 처음 받은 상태인 경우, discovery 용도로 등록한다.
    if Options["mqtt"]["_discovery"] and not last.get(idn):
        # 전등 때문에 last query도 필요... 지금 패킷과 일치하는지 검증
        # gas valve는 일치하지 않는다
        # KTDO: EzVille은 표준 기반이라 Query와 비교 필요 없음.
        # if last_query[1] == packet[1] or device == "gas_valve":
        #    serial_new_device(device, idn, packet)
        #    last[idn] = True

        serial_new_device(device, packet)
        last[idn] = True

        # 장치 등록 먼저 하고, 상태 등록은 그 다음 턴에 한다. (난방 상태 등록 무시되는 현상 방지)
        return

    else:
        last[idn] = packet

    # KTDO: 아래 코드로 값을 바로 판별
    prefix = Options["mqtt"]["prefix"]

    if device == "light":
        grp_id = int(packet[2] >> 4)
        rm_id = int(packet[2] & 0x0F)
        light_count = int(packet[4]) - 1

        for id in range(1, light_count + 1):
            topic = "{}/{}/{}_{}_{}/power/state".format(
                prefix, device, grp_id, rm_id, id
            )

            if packet[5 + id] & 1:
                value = "ON"
            else:
                value = "OFF"

            if last_topic_list.get(topic) != value:
                logger.info(
                    "publish to HA:   {} = {} ({})".format(topic, value, packet.hex())
                )
                mqtt.publish(topic, value)
                last_topic_list[topic] = value

    elif device == "thermostat":
        grp_id = int(packet[2] >> 4)
        room_count = int((int(packet[4]) - 5) / 2)

        for id in range(1, room_count + 1):
            topic1 = "{}/{}/{}_{}/power/state".format(prefix, device, grp_id, id)
            topic2 = "{}/{}/{}_{}/away/state".format(prefix, device, grp_id, id)
            topic3 = "{}/{}/{}_{}/target/state".format(prefix, device, grp_id, id)
            topic4 = "{}/{}/{}_{}/current/state".format(prefix, device, grp_id, id)

            if ((packet[6] & 0x1F) >> (room_count - id)) & 1:
                value1 = "ON"
            else:
                value1 = "OFF"
            if ((packet[7] & 0x1F) >> (room_count - id)) & 1:
                value2 = "ON"
            else:
                value2 = "OFF"
            value3 = packet[8 + id * 2]
            value4 = packet[9 + id * 2]

            if last_topic_list.get(topic1) != value1:
                logger.info(
                    "publish to HA:   {} = {} ({})".format(topic1, value1, packet.hex())
                )
                mqtt.publish(topic1, value1)
                last_topic_list[topic1] = value1
            if last_topic_list.get(topic2) != value2:
                logger.info(
                    "publish to HA:   {} = {} ({})".format(topic2, value2, packet.hex())
                )
                mqtt.publish(topic2, value2)
                last_topic_list[topic2] = value2
            if last_topic_list.get(topic3) != value3:
                logger.info(
                    "publish to HA:   {} = {} ({})".format(topic3, value3, packet.hex())
                )
                mqtt.publish(topic3, value3)
                last_topic_list[topic3] = value3
            if last_topic_list.get(topic4) != value4:
                logger.info(
                    "publish to HA:   {} = {} ({})".format(topic4, value4, packet.hex())
                )
                mqtt.publish(topic4, value4)
                last_topic_list[topic4] = value4


# KTDO: 위의 코드로 대체
#    # device 종류에 따라 전송할 데이터 정리
#    value_list = []
#    for parse in form["parse"]:
#        value_list += serial_peek_value(parse, packet)
#
#    # MQTT topic 형태로 변환, 이전 상태와 같은지 한번 더 확인해서 무시하거나 publish
#    for attr, value in value_list:
#        prefix = Options["mqtt"]["prefix"]
#        topic = "{}/{}/{:x}/{}/state".format(prefix, device, idn, attr)
#        if last_topic_list.get(topic) == value: continue
#
#        if attr != "current":  # 전력사용량이나 현재온도는 너무 자주 바뀌어서 로그 제외
#            logger.info("publish to HA:   {} = {} ({})".format(topic, value, packet.hex()))
#        mqtt.publish(topic, value)
#        last_topic_list[topic] = value


# KTDO: 수정 완료
def serial_get_header():
    try:
        # 0x80보다 큰 byte가 나올 때까지 대기
        # KTDO: 시작 F7 찾기
        while 1:
            header_0 = conn.recv(1)[0]
            # if header_0 >= 0x80: break
            if header_0 == 0xF7:
                break

        # 중간에 corrupt되는 data가 있으므로 연속으로 0x80보다 큰 byte가 나오면 먼젓번은 무시한다
        # KTDO: 연속 0xF7 무시
        while 1:
            header_1 = conn.recv(1)[0]
            # if header_1 < 0x80: break
            if header_1 != 0xF7:
                break
            header_0 = header_1

        header_2 = conn.recv(1)[0]
        header_3 = conn.recv(1)[0]

    except (OSError, serial.SerialException):
        logger.error("ignore exception!")
        header_0 = header_1 = header_2 = header_3 = 0

    # 헤더 반환
    return header_0, header_1, header_2, header_3


# KTDO: 수정 완료
def serial_ack_command(packet):
    logger.info("ack from device: {} ({:x})".format(serial_ack[packet].hex(), packet))

    # 성공한 명령을 지움
    serial_queue.pop(serial_ack[packet], None)
    serial_ack.pop(packet)


# KTDO: 수정 완료
def serial_send_command():
    # 한번에 여러개 보내면 응답이랑 꼬여서 망함
    cmd = next(iter(serial_queue))
    conn.send(cmd)

    # ack = bytearray(cmd[0:3])
    # KTDO: Ezville은 4 Byte까지 확인 필요
    ack = bytearray(cmd[0:4])
    ack[3] = ACK_MAP[cmd[1]][cmd[3]]
    waive_ack = False
    if ack[3] == 0x00:
        waive_ack = True
    ack = int.from_bytes(ack, "big")

    # retry time 관리, 초과했으면 제거
    elapsed = time.time() - serial_queue[cmd]
    if elapsed > Options["rs485"]["max_retry"]:
        logger.error("send to device:  {} max retry time exceeded!".format(cmd.hex()))
        serial_queue.pop(cmd)
        serial_ack.pop(ack, None)
    elif elapsed > 3:
        logger.warning(
            "send to device:  {}, try another {:.01f} seconds...".format(
                cmd.hex(), Options["rs485"]["max_retry"] - elapsed
            )
        )
        serial_ack[ack] = cmd
    elif waive_ack:
        logger.info("waive ack:  {}".format(cmd.hex()))
        serial_queue.pop(cmd)
        serial_ack.pop(ack, None)
    else:
        logger.info("send to device:  {}".format(cmd.hex()))
        serial_ack[ack] = cmd


# KTDO: 수정 완료
def serial_loop():
    logger.info("start loop ...")
    loop_count = 0
    scan_count = 0
    send_aggressive = False

    start_time = time.time()
    while True:
        # 로그 출력
        sys.stdout.flush()

        # 첫 Byte만 0x80보다 큰 두 Byte를 찾음
        header_0, header_1, header_2, header_3 = serial_get_header()
        # KTDO: 패킷단위로 분석할 것이라 합치지 않음.
        # header = (header_0 << 8) | header_1

        # KTDO: Virtual Device는 Skip
        #        # 요청했던 동작의 ack 왔는지 확인
        #        if header in virtual_ack:
        #            virtual_clear(header)
        #
        #        # 인터폰 availability 관련 헤더인지 확인
        #        if header in virtual_avail:
        #            virtual_enable(header_0, header_1)
        #
        #        # 가상 장치로써 응답해야 할 header인지 확인
        #        if header_0 in header_0_virtual:
        #            virtual_query(header_0, header_1)

        # KTDO: int('20', base=16)
        # device로부터의 state 응답이면 확인해서 필요시 HA로 전송해야 함
        if header_1 in STATE_HEADER and header_3 in STATE_HEADER[header_1]:
            # packet = bytes([header_0, header_1])

            # 몇 Byte짜리 패킷인지 확인
            # device, remain = STATE_HEADER[header]
            device = STATE_HEADER[header_1][0]
            # KTDO: 데이터 길이는 다음 패킷에서 확인
            header_4 = conn.recv(1)[0]
            data_length = int(header_4)

            # KTDO: packet 생성 위치 변경
            packet = bytes([header_0, header_1, header_2, header_3, header_4])

            # 해당 길이만큼 읽음
            # KTDO: 데이터 길이 + 2 (XOR + ADD) 만큼 읽음
            packet += conn.recv(data_length + 2)

            # checksum 오류 없는지 확인
            # KTDO: checksum 및 ADD 오류 없는지 확인
            if not serial_verify_checksum(packet):
                continue

            # 디바이스 응답 뒤에도 명령 보내봄
            if serial_queue and not conn.check_pending_recv():
                serial_send_command()
                conn.set_pending_recv()

            # 적절히 처리한다
            serial_receive_state(device, packet)

        # KTDO: 이전 명령의 ACK 경우
        elif header_1 in ACK_HEADER and header_3 in ACK_HEADER[header_1]:
            # 한 byte 더 뽑아서, 보냈던 명령의 ack인지 확인
            # header_2 = conn.recv(1)[0]
            # header = (header << 8) | header_2
            header = header_0 << 24 | header_1 << 16 | header_2 << 8 | header_3

            if header in serial_ack:
                serial_ack_command(header)

        # KTDO: 필요 없음.
        # 마지막으로 받은 query를 저장해둔다 (조명 discovery에 필요)
        # elif header in QUERY_HEADER:
        #    # 나머지 더 뽑아서 저장
        #    global last_query
        #    packet = conn.recv(QUERY_HEADER[header][1])
        #    packet = header.to_bytes(2, "big") + packet
        #    last_query = packet

        # 명령을 보낼 타이밍인지 확인: 0xXX5A 는 장치가 있는지 찾는 동작이므로,
        # 아직도 이러고 있다는건 아무도 응답을 안할걸로 예상, 그 타이밍에 끼어든다.
        # KTDO: EzVille은 표준에 따라 Ack 이후 다음 Request 까지의 시간 활용하여 command 전송
        #       즉 State 확인 후에만 전달
        elif (header_3 == 0x81 or 0x8F or 0x0F) or send_aggressive:
            # if header_1 == HEADER_1_SCAN or send_aggressive:
            scan_count += 1
            if serial_queue and not conn.check_pending_recv():
                serial_send_command()
                conn.set_pending_recv()

        # 전체 루프 수 카운트
        # KTDO: 가스 밸브 쿼리로 확인
        global HEADER_0_FIRST
        # KTDO: 2번째 Header가 장치 Header임
        if header_1 == HEADER_0_FIRST[0][0] and (
            header_3 == HEADER_0_FIRST[0][1] or header_3 == HEADER_0_FIRST[1][1]
        ):
            loop_count += 1

            # 돌만큼 돌았으면 상황 판단
            if loop_count == 30:
                # discovery: 가끔 비트가 튈때 이상한 장치가 등록되는걸 막기 위해, 시간제한을 둠
                if Options["mqtt"]["_discovery"]:
                    logger.info("Add new device:  All done.")
                    Options["mqtt"]["_discovery"] = False
                else:
                    logger.info("running stable...")

                # 스캔이 없거나 적으면, 명령을 내릴 타이밍을 못잡는걸로 판단, 아무때나 닥치는대로 보내봐야한다.
                if Options["serial_mode"] == "serial" and scan_count < 30:
                    logger.warning("initiate aggressive send mode!", scan_count)
                    send_aggressive = True

            # HA 재시작한 경우
            elif loop_count > 30 and Options["mqtt"]["_discovery"]:
                loop_count = 1

        # 루프 카운트 세는데 실패하면 다른 걸로 시도해봄
        if loop_count == 0 and time.time() - start_time > 6:
            print(
                "check loop count fail: there are no F7 {:02X} ** {:02X} or F7 {:02X} ** {:02X}! try F7 {:02X} ** {:02X} or F7 {:02X} ** {:02X}...".format(
                    HEADER_0_FIRST[0][0],
                    HEADER_0_FIRST[0][1],
                    HEADER_0_FIRST[1][0],
                    HEADER_0_FIRST[1][1],
                    header_0_first_candidate[-1][0][0],
                    header_0_first_candidate[-1][0][1],
                    header_0_first_candidate[-1][1][0],
                    header_0_first_candidate[-1][1][1],
                )
            )
            HEADER_0_FIRST = header_0_first_candidate.pop()
            start_time = time.time()
            scan_count = 0


# KTDO: 수정 완료
def dump_loop():
    dump_time = Options["rs485"]["dump_time"]

    if dump_time > 0:
        if dump_time < 10:
            logger.warning(
                "dump_time is too short! automatically changed to 10 seconds..."
            )
            dump_time = 10

        start_time = time.time()
        logger.warning("packet dump for {} seconds!".format(dump_time))

        conn.set_timeout(2)
        logs = []
        while time.time() - start_time < dump_time:
            try:
                data = conn.recv(256)
            except:
                continue

            if data:
                for b in data:
                    if b == 0xF7 or len(logs) > 500:
                        logger.info("".join(logs))
                        logs = ["{:02X}".format(b)]
                    else:
                        logs.append(",  {:02X}".format(b))
        logger.info("".join(logs))
        logger.warning("dump done.")
        conn.set_timeout(None)


if __name__ == "__main__":
    global conn

    # configuration 로드 및 로거 설정
    init_logger()
    init_option(sys.argv)
    init_logger_file()

    # KTDO: Virtual Device는 Skip
    #    init_virtual_device()

    if Options["serial_mode"] == "socket":
        logger.info("initialize socket...")
        conn = EzVilleSocket()
    else:
        logger.info("initialize serial...")
        conn = EzVilleSerial()

    dump_loop()

    start_mqtt_loop()

    try:
        # 무한 루프
        serial_loop()
    except:
        logger.exception("addon finished!")
