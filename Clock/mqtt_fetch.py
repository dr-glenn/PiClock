# dht_reader.py
# Getting lots of ideas and code from Steve: http://www.steves-internet-guide.com/client-connections-python-mqtt/
import paho.mqtt.client as mqtt
import time
#import Adafruit_DHT
import logging
if __name__ == '__main__':
    from logging.handlers import RotatingFileHandler,TimedRotatingFileHandler
    #logging.basicConfig(filename='piclock.log', level=logging.WARNING)
    handler = RotatingFileHandler('mqtt.log', maxBytes=50000, backupCount=3)
    #handler = TimedRotatingFileHandler('piclock.log', when='midnight', interval=1, backupCount=3)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s : %(message)s')
    handler.setFormatter(formatter)
    defLogger = logging.getLogger('')
    defLogger.addHandler(handler)
    defLogger.setLevel(logging.DEBUG)
    #logging.basicConfig(filename='mqtt.log', level=logging.WARNING)

logger = logging.getLogger('mqtt')
#logger.setLevel(logging.DEBUG)

# Here are params to connect to Cayenne MQTT
MQTT_HOST = "mqtt.mydevices.com"    # Cayenne services
MQTT_USERNAME  = "3c9f82b0-ae30-11e8-9bc2-335872d4b092"
MQTT_PASSWORD  = "d7e764d9f3df983ac9c302070df769ee8b1e096f"
# Next is ID for this computer:
MQTT_CLIENT_ID = "6d136b90-e7bb-11e8-809d-0f8fe4c30267"
# Here is ClientID for the publisher, a different computer:
PUB_CLIENT_ID = "5df2add0-af06-11e8-85ea-f10189fd2756"

# v1/username/things/clientID/data/channel
TOPIC = "v1/%s/things/%s/data/%d"   # last arg is channel number
TOPIC3= TOPIC %(MQTT_USERNAME,PUB_CLIENT_ID,3) # DHT22 temperature
TOPIC4= TOPIC %(MQTT_USERNAME,PUB_CLIENT_ID,4) # DHT22 humidity
msg_dict = {}

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.connected_flag = True
        logger.info("connected OK")
        my_subscribe(client)
    else:
        logger.error("Bad connection, returned code=%d"%(rc))
        client.bad_connection_flag = True

def on_disconnect(client, userdata, rc):
    logging.info("disconnecting reason  "  +str(rc))
    client.connected_flag=False
    client.disconnect_flag=True

def on_message(mclient, userdata, message):
    global msg_dict
    msg = str(message.payload.decode("utf-8"))
    logger.info("received message =%s" %(msg))
    # message looks like: "temp,c=22.200" or "rel_hum,p=48.5"
    param,value = msg.split(',')
    unit,fvalue = value.split('=')
    # put info back to somebody
    # TODO: should be using user_data_set(), so that "userdata" has useful content.
    msg_dict[param] = fvalue
    #time.sleep(1)
    mclient.has_message = True

def on_subscribe(mclient, userdata, mid, granted_qos):
    logger.info("Subscribed: %s" %(str(mid)+" "+str(granted_qos)))

def my_connect():
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, transport="tcp", protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    #client.begin(MQTT_USERNAME, MQTT_PASSWORD, MQTT_CLIENT_ID)
    client.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)
    # Steve recommends adding a connect flag:
    client.connected_flag = False
    client.bad_connection_flag = False
    # GDN: I don't know what happens in the client loop, but I have a theory!
    # The keepalive parameter tells the broker that it should expect either a MQTT packet
    # or at least a PINGREQ packet. If not, then when timeout is reached the broker will
    # close the connection. I believe that loop_start creates a loop that guarantees at least
    # a PINGREQ gets sent.
    # This article is very helpful: https://www.hivemq.com/blog/mqtt-essentials-part-10-alive-client-take-over
    # If the broker decides to timeout the connection, the client will have to reestablish.
    client.connect(MQTT_HOST, port=1883, keepalive=60, bind_address="")
    client.loop_start()
    while not client.connected_flag:
        logger.info("Wait for connect")
        time.sleep(1)
    return client

def my_subscribe(client, message_store = None):
    logger.info("Start Main loop")
    client.has_message = False
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    result,msg_id = client.subscribe(TOPIC3)
    logger.debug('subscribe: result=%s, msg_id=%s' %(str(result),str(msg_id)))
    result,msg_id = client.subscribe(TOPIC4)
    logger.debug('subscribe: result=%s, msg_id=%s' %(str(result),str(msg_id)))

def run_as_service():
    logger.debug("run_as_service")
    client = my_connect()
    #my_subscribe(client)
    # Messages will be found in msg_dict
    
msg_max = 2
msg_cnt = 0
def run_as_main():
    '''
    Run until we reach msg_max, then exit
    '''
    global msg_cnt, msg_max
    logger.debug("run_as_main")
    client = my_connect()
    my_subscribe(client)
    time_cnt = 0
    try:
        while msg_cnt < msg_max:
            while not client.has_message:
                time.sleep(5)
                time_cnt += 5
                logger.debug("waiting for message, t=%d" %(time_cnt))
            client.has_message = False
            msg_cnt += 1
    except (KeyboardInterrupt, SystemExit):
        logger.info("interrupt")
        #raise
    finally:
        print "Proper MQTT shutdown"
        logger.info("Proper MQTT shutdown")
        client.unsubscribe(TOPIC3)
        client.unsubscribe(TOPIC4)
        client.disconnect()
        client.loop_stop()

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    run_as_main()
    #run_as_service()
    logger.info("Last values: "+str(msg_dict))

