# first written by nandflash("저장장치") <github@printk.info> since 2020-06-25
# Second Modify by KT("ktdo79") <ktdo79@gmail.com> since 2022-06-25

# This is a part of EzVille Wallpad Addon for Home Assistant
# Author: Dong SHIN <d0104.shin@gmail.com> 2024-02-15

import socket
import threading
import serial
import paho.mqtt.client as paho_mqtt
import json

import sys
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from collections import defaultdict
import os.path
import re

RS485_DEVICE = {
    "light": {
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
    "thermostat": {
        "state": {
            "id": 0x36,
            "cmd": 0x81,
        },
        "last": {},
        "away": {
            "id": 0x36,
            "cmd": 0x46,
            "ack": 0xC6,
        },
        "target": {
            "id": 0x36,
            "cmd": 0x44,
            "ack": 0xC4,
        },
        "power": {
            "id": 0x36,
            "cmd": 0x43,
            "ack": 0xC3,
        },
    },
    "batch": {  # 안보임
        "state": {"id": 0x33, "cmd": 0x81},
        "press": {"id": 0x33, "cmd": 0x41, "ack": 0xC1},
    },
    "plug": {
        "state": {"id": 0x39, "cmd": 0x81},
        "power": {"id": 0x39, "cmd": 0x41, "ack": 0xC1},
    },
}

DISCOVERY_DEVICE = {
    "ids": [
        "ezville_wallpad",
    ],
    "name": "ezville_wallpad",
    "mf": "EzVille",
    "mdl": "EzVille Wallpad",
    "sw": "dongs0104/ha_addons/ezville_wallpad",
}

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
    "thermostat": [
        {
            "_intg": "climate",
            "~": "{prefix}/thermostat/{grp}_{id}",
            "name": "{prefix}_thermostat_{grp}_{id}",
            "mode_stat_t": "~/power/state",
            "mode_cmd_t": "~/power/command",
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
    "plug": [
        {
            "_intg": "switch",
            "~": "{prefix}/plug/{idn}/power",
            "name": "{prefix}_plug_{idn}",
            "stat_t": "~/state",
            "cmd_t": "~/command",
            "icon": "mdi:power-plug",
        },
        {
            "_intg": "sensor",
            "~": "{prefix}/plug/{idn}",
            "name": "{prefix}_plug_{idn}_power_usage",
            "stat_t": "~/current/state",
            "unit_of_meas": "W",
        },
    ],
    "cutoff": [
        {
            "_intg": "switch",
            "~": "{prefix}/cutoff/{idn}/power",
            "name": "{prefix}_light_cutoff_{idn}",
            "stat_t": "~/state",
            "cmd_t": "~/command",
        }
    ],
    "energy": [
        {
            "_intg": "sensor",
            "~": "{prefix}/energy/{idn}",
            "name": "_",
            "stat_t": "~/current/state",
            "unit_of_meas": "_",
            "val_tpl": "_",
        }
    ],
}

STATE_HEADER = {
    prop["state"]["id"]: (device, prop["state"]["cmd"])
    for device, prop in RS485_DEVICE.items()
    if "state" in prop
}
# 제어 명령의 ACK header만 모음
ACK_HEADER = {
    prop[cmd]["id"]: (device, prop[cmd]["ack"])
    for device, prop in RS485_DEVICE.items()
    for cmd, code in prop.items()
    if "ack" in code
}
# KTDO: 제어 명령과 ACK의 Pair 저장

ACK_MAP = defaultdict(lambda: defaultdict(dict))
for device, prop in RS485_DEVICE.items():
    for cmd, code in prop.items():
        if "ack" in code:
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
    def __init__(self, addr, port, capabilities="ALL"):
        self.capabilities = capabilities
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
            new_data = self._recv_raw(128)
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
            new_data = self._recv_raw(128)
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

    with open(default_file, encoding="utf-8") as f:
        config = json.load(f)
        logger.info("addon version %s", config["version"])
        Options = config["options"]
    with open(option_file, encoding="utf-8") as f:
        Options2 = json.load(f)

    # 업데이트
    for k, v in Options.items():
        if isinstance(v, dict) and k in Options2:
            Options[k].update(Options2[k])
            for k2 in Options[k].keys():
                if k2 not in Options2[k].keys():
                    logger.warning(
                        "no configuration value for '%s:%s'! try default value (%s)...",
                        k,
                        k2,
                        Options[k][k2],
                    )
        else:
            if k not in Options2:
                logger.warning(
                    "no configuration value for '%s'! try default value (%s)...",
                    k,
                    Options[k],
                )
            else:
                Options[k] = Options2[k]

    # 관용성 확보
    Options["mqtt"]["server"] = re.sub("[a-z]*://", "", Options["mqtt"]["server"])
    if Options["mqtt"]["server"] == "127.0.0.1":
        logger.warning("MQTT server address should be changed!")

    # internal options
    Options["mqtt"]["_discovery"] = Options["mqtt"]["discovery"]


# KTDO: 수정 완료
def mqtt_discovery(payload):
    """
    Publishes MQTT discovery message for a new device.

    Args:
        payload (dict): The payload containing device information.

    Returns:
        None
    """
    intg = payload.pop("_intg")

    # MQTT 통합구성요소에 등록되기 위한 추가 내용
    payload["device"] = DISCOVERY_DEVICE
    payload["uniq_id"] = payload["name"]

    # discovery에 등록
    topic = f"homeassistant/{intg}/ezville_wallpad/{payload['name']}/config"
    logger.info("Add new device: %s", topic)
    mqtt.publish(topic, json.dumps(payload))


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

    # 오류 체크 끝났으면 serial 메시지 생성
    cmd = RS485_DEVICE[device][cmd]
    packet = None
    if device == "light":
        if payload == "ON":
            payload = 0xF1 if idn.startswith("1_1") else 0x01  # 거실등만 0xF1
        elif payload == "OFF":
            payload = 0x00
        length = 10
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x03
        packet[5] = int(idn.split("_")[2])
        packet[6] = payload
        packet[7] = 0x00
        packet[8], packet[9] = serial_generate_checksum(packet)
    elif device == "thermostat":
        if payload == "heat":
            payload = 0x01
        elif payload == "off":
            payload = 0x00
        length = 8
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x01
        packet[5] = int(float(payload))
        packet[6], packet[7] = serial_generate_checksum(packet)
    # TODO : gasvalve, batch, plug
    elif device == "plug":
        length = 8
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x01
        packet[5] = 0x11 if payload == "ON" else 0x10
        packet[6], packet[7] = serial_generate_checksum(packet)
    if packet:
        packet = bytes(packet)
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

    logger.info("recv. from HA:   %s = %s", msg.topic, payload)

    device = topics[1]
    if device == "status":
        if payload == "online":
            mqtt_init_discovery()
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
        logger.error("MQTT connection return with:  %s", paho_mqtt.connack_string(rc))

    mqtt_init_discovery()

    topic = "homeassistant/status"
    logger.info("subscribe %s", topic)
    mqtt.subscribe(topic, 0)

    prefix = Options["mqtt"]["prefix"]
    if Options["wallpad_mode"] != "off":
        topic = f"{prefix}/+/+/+/command"
        logger.info("subscribe %s", topic)
        mqtt.subscribe(topic, 0)


# KTDO: 수정 완료
def mqtt_on_disconnect(client, userdata, flags, rc, properties):
    logger.warning("MQTT disconnected! (%s)", rc)
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
        logger.error("MQTT server address/port may be incorrect! (%s)", e)
        sys.exit(1)

    mqtt.loop_start()

    delay = 1
    while not mqtt_connected:
        logger.info("waiting MQTT connected ...")
        time.sleep(delay)
        delay = min(delay * 2, 10)


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
    return checksum, add


# KTDO: 수정 완료
def serial_new_device(device, packet, idn=None):
    prefix = Options["mqtt"]["prefix"]
    # 조명은 두 id를 조합해서 개수와 번호를 정해야 함
    if device == "light":
        # KTDO: EzVille에 맞게 수정
        grp_id = int(packet[2] >> 4)
        rm_id = int(packet[2] & 0x0F)
        light_count = int(packet[4]) - 1
        for light_id in range(1, light_count + 1):
            payload = DISCOVERY_PAYLOAD[device][0].copy()
            payload["~"] = payload["~"].format(
                prefix=prefix, grp=grp_id, rm=rm_id, id=light_id
            )
            payload["name"] = payload["name"].format(
                prefix=prefix, grp=grp_id, rm=rm_id, id=light_id
            )

            mqtt_discovery(payload)

    elif device == "thermostat":
        # KTDO: EzVille에 맞게 수정
        grp_id = int(packet[2] >> 4)
        room_count = int((int(packet[4]) - 5) / 2)
        
        for room_id in range(1, room_count + 1):
            payload = DISCOVERY_PAYLOAD[device][0].copy()
            payload["~"] = payload["~"].format(prefix=prefix, grp=grp_id, id=room_id)
            payload["name"] = payload["name"].format(prefix=prefix, grp=grp_id, id=room_id)

            mqtt_discovery(payload)

    elif device == "plug":
        # KTDO: EzVille에 맞게 수정
        grp_id = int(packet[2] >> 4)
        plug_count = int(packet[4] / 3)
        for plug_id in range(1, plug_count + 1):
            payload = DISCOVERY_PAYLOAD[device][0].copy()
            payload["~"] = payload["~"].format(prefix=prefix, idn=f"{grp_id}_{plug_id}")
            payload["name"] = payload["name"].format(
                prefix=prefix, idn=f"{grp_id}_{plug_id}"
            )

            mqtt_discovery(payload)

    elif device in DISCOVERY_PAYLOAD:
        for payloads in DISCOVERY_PAYLOAD[device]:
            payload = payloads.copy()

            payload["~"] = payload["~"].format(prefix=prefix, idn=idn)
            payload["name"] = payload["name"].format(prefix=prefix, idn=idn)

            # 실시간 에너지 사용량에는 적절한 이름과 단위를 붙여준다 (단위가 없으면 그래프로 출력이 안됨)
            # KTDO: Ezville에 에너지 확인 쿼리 없음
            if device == "energy":
                payload["name"] = "{}_{}_consumption".format(
                    prefix, ("power", "gas", "water")[idn]
                )
                payload["unit_of_meas"] = ("W", "m³/h", "m³/h")[idn]
                payload["val_tpl"] = (
                    "{{ value }}",
                    "{{ value | float / 100 }}",
                    "{{ value | float / 100 }}",
                )[idn]

            mqtt_discovery(payload)


# KTDO: 수정 완료
def serial_receive_state(device, packet):
    form = RS485_DEVICE[device]["state"]
    last = RS485_DEVICE[device]["last"]
    idn = (packet[1] << 8) | packet[2]
    # 해당 ID의 이전 상태와 같은 경우 바로 무시
    if last.get(idn) == packet:
        return

    # 처음 받은 상태인 경우, discovery 용도로 등록한다.
    if Options["mqtt"]["_discovery"] and not last.get(idn):
        serial_new_device(device, packet, idn)
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

        for light_id in range(1, light_count + 1):
            topic = f"{prefix}/{device}/{grp_id}_{rm_id}_{light_id}/power/state"
            if packet[5 + light_id] & 1:
                value = "ON"
            else:
                value = "OFF"

            if last_topic_list.get(topic) != value:
                logger.debug("publish to HA:   %s = %s (%s)", topic, value, packet.hex())
                mqtt.publish(topic, value)
                last_topic_list[topic] = value

    elif device == "thermostat":
        grp_id = int(packet[2] >> 4)
        room_count = int((int(packet[4]) - 5) / 2)

        for thermostat_id in range(1, room_count + 1):
            if ((packet[6] & 0x1F) >> (room_count - thermostat_id)) & 1:
                value1 = "ON"
            else:
                value1 = "OFF"
            if ((packet[7] & 0x1F) >> (room_count - thermostat_id)) & 1:
                value2 = "ON"
            else:
                value2 = "OFF"
            for sub_topic, value in zip(
                ["mode", "away", "target", "current"],
                [
                    value1,
                    value2,
                    packet[8 + thermostat_id * 2],
                    packet[9 + thermostat_id * 2],
                ],
            ):
                topic = f"{prefix}/{device}/{grp_id}_{thermostat_id}/{sub_topic}/state"
                if last_topic_list.get(topic) != value:
                    logger.debug(
                        "publish to HA:   %s = %s (%s)", topic, value, packet.hex()
                    )
                    mqtt.publish(topic, value)
                    last_topic_list[topic] = value
    elif device == "plug":
        grp_id = int(packet[2] >> 4)
        plug_count = int(packet[4] / 3)
        for plug_id in range(1, plug_count + 1):
            for sub_topic, value in zip(
                ["power", "current"],
                [
                    "ON" if packet[plug_id * 3 + 3] & 0x10 else "OFF",
                    f"{format(packet[plug_id * 3 + 4], 'x')}.{format(packet[plug_id * 3 + 5], 'x')}",
                ],
            ):
                topic = f"{prefix}/{device}/{grp_id}_{plug_id}/{sub_topic}/state"
                if last_topic_list.get(topic) != value:
                    logger.debug(
                        "publish to HA:   %s = %s (%s)", topic, value, packet.hex()
                    )
                    mqtt.publish(topic, value)
                    last_topic_list[topic] = value


# KTDO: 수정 완료
def serial_get_header(conn):
    try:
        # 0x80보다 큰 byte가 나올 때까지 대기
        # KTDO: 시작 F7 찾기
        while True:
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
def serial_send_command(conn):
    # 한번에 여러개 보내면 응답이랑 꼬여서 망함
    cmd = next(iter(serial_queue))
    if conn.capabilities != "ALL" and ACK_HEADER[cmd[1]][0] not in conn.capabilities:
        return
    conn.send(cmd)
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
        logger.error("send to device:  %s max retry time exceeded!", cmd.hex())
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
        logger.info("waive ack:  %s", cmd.hex())
        serial_queue.pop(cmd)
        serial_ack.pop(ack, None)
    else:
        logger.info("send to device:  %s", cmd.hex())
        serial_ack[ack] = cmd


# KTDO: 수정 완료
def daemon(conn):
    logger.info("start loop ...")
    scan_count = 0
    send_aggressive = False
    while True:
        # 로그 출력
        sys.stdout.flush()

        # 첫 Byte만 0x80보다 큰 두 Byte를 찾음
        header_0, header_1, header_2, header_3 = serial_get_header(conn)
        # KTDO: 패킷단위로 분석할 것이라 합치지 않음.
        # header = (header_0 << 8) | header_1
        # device로부터의 state 응답이면 확인해서 필요시 HA로 전송해야 함
        if header_1 in STATE_HEADER and header_3 in STATE_HEADER[header_1]:
            device = STATE_HEADER[header_1][0]
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
                serial_send_command(conn=conn)
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

        # 명령을 보낼 타이밍인지 확인: 0xXX5A 는 장치가 있는지 찾는 동작이므로,
        # 아직도 이러고 있다는건 아무도 응답을 안할걸로 예상, 그 타이밍에 끼어든다.
        # KTDO: EzVille은 표준에 따라 Ack 이후 다음 Request 까지의 시간 활용하여 command 전송
        #       즉 State 확인 후에만 전달
        elif (header_3 == 0x81 or 0x8F or 0x0F) or send_aggressive:
            # if header_1 == HEADER_1_SCAN or send_aggressive:
            scan_count += 1
            if serial_queue and not conn.check_pending_recv():
                serial_send_command(conn=conn)
                conn.set_pending_recv()


# KTDO: 수정 완료
def init_connect(conn):
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
                data = conn.recv(128)
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
    # configuration 로드 및 로거 설정
    init_logger()
    init_option(sys.argv)
    init_logger_file()
    start_mqtt_loop()

    if Options["serial_mode"] == "sockets":
        for _socket in Options["sockets"]:
            conn = EzVilleSocket(_socket["address"], _socket["port"], _socket["capabilities"])
            init_connect(conn=conn)
            thread = threading.Thread(target=daemon, args=(conn,))
            thread.daemon = True
            thread.start()
        while True:
            time.sleep(10**8)
    elif Options["serial_mode"] == "socket":
        logger.info("initialize socket...")
        conn = EzVilleSocket(Options["socket"]["address"], Options["socket"]["port"])
    else:
        logger.info("initialize serial...")
        conn = EzVilleSerial()
    if Options["serial_mode"] != "sockets":
        init_connect(conn=conn)
        try:
            daemon(conn=conn)
        except:
            logger.exception("addon finished!")
