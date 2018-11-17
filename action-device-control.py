#!/usr/bin/env python2
from hermes_python.hermes import Hermes
import paho.mqtt.client as mqtt
import time
from pprint import pprint

USERNAME_PREFIX = "kblachowicz:"
MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

# Answers slots
INTENT_DEVICE = USERNAME_PREFIX + "Device"
INTENT_INTERRUPT = USERNAME_PREFIX + "Interrupt"
INTENT_DOES_NOT_KNOW = USERNAME_PREFIX + "DoesNotKnow"

INTENT_FILTER_START_SESSION = [
    USERNAME_PREFIX + "TurnOn",
    USERNAME_PREFIX + "TurnOff",
    USERNAME_PREFIX + "Mute",
    USERNAME_PREFIX + "Unmute",
    USERNAME_PREFIX + "Play",
    USERNAME_PREFIX + "Pause",
    USERNAME_PREFIX + "Stop"
]

INTENT_FILTER_GET_ANSWER = [
    INTENT_DEVICE,
    INTENT_INTERRUPT,
    INTENT_DOES_NOT_KNOW
]

SessionsStates = {}


def _set_not_none_dict_value(to_update, update):
    to_update = to_update or {}
    for key, value in update.iteritems():
        if value is not None:
            to_update[key] = value
    return to_update


def save_session_state(sessions_states, session_id, new_state):
    sessions_states[session_id] = _set_not_none_dict_value(sessions_states.get(session_id), new_state)


def remove_session_state(sessions_states, session_id):
    sessions_states[session_id] = None


def put_mqtt(ip, port, topic, payload, username, password):
    client = mqtt.Client("Client")  # create new instance
    client.username_pw_set(username, password)
    client.connect(ip, port)  # connect to broker
    if isinstance(payload, basestring):
        payload = [payload]
    payload_count = len(payload)
    for p in payload:
        print "Publishing " + topic + " / " + p.lower()
        msg = client.publish(topic, p.lower())
        if msg is not None:
            msg.wait_for_publish()
        if payload_count > 1:
            time.sleep(100.0 / 1000.0)
    client.disconnect()


def get_intent_msg(intent_message):
    return intent_message.intent.intent_name.split(':')[-1]


def get_devices(intent_message):
    devices_count = len(intent_message.slots.device)
    devices = []
    for x in range(devices_count):
        devices.append(intent_message.slots.device[x].slot_value.value.value)
    return devices


def start_session(hermes, intent_message):
    session_id = intent_message.session_id
    intent_msg_name = intent_message.intent.intent_name
    if intent_msg_name not in INTENT_FILTER_START_SESSION:
        return

    print "Starting device control session " + session_id
    session_state = {"topic": get_intent_msg(intent_message), "device": []}

    device = intent_message.slots.device.first()
    if device is None:
        save_session_state(SessionsStates, session_id, session_state)
        hermes.publish_continue_session(session_id,
                                        "What do you want to " + session_state.get("topic").split(':')[-1] + "?",
                                        INTENT_FILTER_GET_ANSWER)
    else:
        session_state["device"] = get_devices(intent_message)
        put_mqtt(MQTT_IP_ADDR, MQTT_PORT, session_state.get("topic"), session_state.get("device"), None, None)
        hermes.publish_end_session(session_id, None)


def user_gives_answer(hermes, intent_message):
    print("User is giving an answer")
    session_id = intent_message.session_id
    print session_id
    session_state = SessionsStates.get(session_id)
    session_state, sentence, continues = check_user_answer(session_state, intent_message)

    print session_state.get("device")
    if not continues:
        put_mqtt(MQTT_IP_ADDR, MQTT_PORT, session_state.get("topic"), session_state.get("device"), None, None)
        remove_session_state(SessionsStates, session_id)
        hermes.publish_end_session(session_id, None)
        return

    hermes.publish_continue_session(session_id, sentence, INTENT_FILTER_GET_ANSWER)


def user_quits(hermes, intent_message):
    print("User wants to quit")
    session_id = intent_message.session_id

    remove_session_state(SessionsStates, session_id)
    hermes.publish_end_session(session_id, "OK, no problem")


def check_user_answer(session_state, intent_message):
    if session_state is None:
        print "Error: session_state is None ==> intent triggered outside of dialog session"
        return session_state, "", False

    devices = get_devices(intent_message)
    # We just try keep listening to the user until we get an answer
    if len(devices) == 0:
        return session_state, "Please repeat", True

    session_state["device"] = devices
    return session_state, "", False


def session_started(hermes, session_ended_message):
    return


def session_ended(hermes, session_ended_message):
    return


with Hermes(MQTT_ADDR) as h:
    h.subscribe_intents(start_session) \
        .subscribe_intent(INTENT_INTERRUPT, user_quits) \
        .subscribe_intent(INTENT_DEVICE, user_gives_answer) \
        .subscribe_session_ended(session_ended) \
        .subscribe_session_started(session_started) \
        .start()
