import server

import pika
from msgpack import packb
import signal

from json import loads as json_loads

import sys
from sys import stderr

mq_i = 0
exiting = False

to_queue_name = os.getenv('TO_QUEUE', 'made-tiles')
failed_queue_name = os.getenv('FAILED_QUEUE', 'failed-tiles')

class Coordinate:
    def __init__(self, row, column, zoom):
        self.row = row
        self.column = column
        self.zoom = zoom

def makeTile(ch, method, properties, data):
    body = json_loads(data)
    coord = Coordinate(body['coord']['row'], body['coord']['col'], body['coord']['zoom'])
    path = '%d/%d/%d' % (coord.zoom, coord.column, coord.row)

    # Fetch a tile.
    rendered = False

    global mq_i
    global exiting

    while not rendered:
        try:
            content = server.get_mvt(coord.zoom, coord.column, coord.row)

            mq_i = mq_i + 1
            if (mq_i % 100 == 0):
                print('ToMQ', mq_i, coord)

            msg = packb({
                "zoom": coord.zoom,
                "column": coord.column,
                "row": coord.row,
                "tile": content
            })

            mq_done_channel.basic_publish(exchange='', routing_key=to_queue_name, body=msg)

        except:
            # Something went wrong: try again? Log the error?

            print('Exception')
            global exiting
            if exiting:
                print('Exiting.')
                ch.close()
                break

            print('Failed', coord, file=sys.stderr)
            global dud_channel
            dud_channel.basic_publish(exchange='', routing_key=failed_queue_name, body=data)
            ch.basic_nack(delivery_tag = method.delivery_tag, requeue=False)
            # MAX_ERRORS?
            #if not error_list:
            raise
            #break

        else:
            # Successfully got the tile.
            rendered = True
            ch.basic_ack(delivery_tag = method.delivery_tag)

def exit_handler(signal, frame):
    global exiting
    exiting = True
    global channel
    global consumer_tag
    print('You pressed Ctrl+C!')
    channel.basic_cancel(consumer_tag=consumer_tag)
    channel.close()

    sys.exit(0)


def m():
    if __name__ == "__main__":
        mq_credentials = pika.PlainCredentials(os.getenv('MQ_USER','mblissett'), os.getenv('MQ_PASSWORD','mblissett'))
        mq_connection = pika.BlockingConnection(pika.ConnectionParameters(os.getenv('MQ_HOST','mq.gbif.org'), os.getenv('MQ_PORT','5672'), os.getenv('MQ_VHOST','/users/mblissett'), mq_credentials))

        global mq_done_channel
        mq_done_channel = mq_connection.channel()
        mq_done_channel.queue_declare(queue=os.getenv('TO_QUEUE','made-tiles'))

        global mq_dud_channel
        mq_dud_channel = mq_connection.channel()
        mq_dud_channel.queue_declare(queue=os.getenv('FAILED_QUEUE','failed-tiles'))

        global mq_channel
        mq_channel = mq_connection.channel()
        mq_channel.queue_declare(queue=os.getenv('FROM_QUEUE','do-tiles'))
        mq_channel.basic_qos(prefetch_count=50)
        global consumer_tag
        consumer_tag = mq_channel.basic_consume(makeTile, queue=os.getenv('FROM_QUEUE','do-tiles'))

        signal.signal(signal.SIGINT, exit_handler)

        print('Waiting for messages. To exit press CTRL+C')
        mq_channel.start_consuming()

m()
