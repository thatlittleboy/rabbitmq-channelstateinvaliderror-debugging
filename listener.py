import asyncio
import sys

import aio_pika
from aio_pika.pool import Pool

from comlog import logger


class InnerFeaturesCallback:
    name = "InnerFeaturesCallback"

    def __init__(self):
        self._inited = False

    async def cb_init(self):
        if self._inited:
            return
        # create db connection, but ignore now...
        logger.info(f"[LISTEN] {self.name} initialized")
        self._inited = True

    async def callback(self, message):
        with message.process():
            routing_key, body = message.routing_key, message.body
            logger.info(
                f"[LISTEN] Routing key: {routing_key}, Message: {body}. "
                "Consuming and inserting into db...",
            )
            # time.sleep(0.2)
            # insert into db skipped


class Consumer:
    def __init__(self, name, callbacks):
        self.name = name
        self.callbacks = callbacks
        self._inited = False

    async def get_connection(self):
        return await aio_pika.connect_robust("amqp://guest:guest@localhost/")

    async def get_channel(self):
        async with self.connection_pool.acquire() as connection:
            return await connection.channel()

    async def get_queue(self, queue_name: str):
        async with self.channel_pool.acquire() as channel:
            logger.info(f"[LISTEN] Get queue: {queue_name}")
            return await channel.get_queue(queue_name, ensure=False)

    async def load_callback(self):
        self._initialized_callbacks = {}
        for callback in self.callbacks:
            tmp = callback()
            await tmp.cb_init()
            self._initialized_callbacks[tmp.name] = tmp

    async def mq_init(self):
        if self._inited:
            return

        try:
            self.connection_pool = Pool(self.get_connection, max_size=1)  # 5
        except Exception as e:
            logger.exception("[LISTEN] " + str(e))
        else:
            logger.info("[LISTEN] Successfully get connection")
        try:
            self.channel_pool = Pool(self.get_channel, max_size=1)  # 10
        except Exception as e:
            logger.exception("[LISTEN] " + str(e))
        else:
            logger.info("[LISTEN] Successfully get channel")
        try:
            await self.load_callback()
        except Exception as e:
            logger.exception("[LISTEN] " + str(e))
        else:
            logger.info(f"[LISTEN] Loaded {list(self._initialized_callbacks.keys())}")
        self._inited = True
        logger.info("[LISTEN] Initialized")

    async def consume(self):
        queue_callback_mapping = {
            "risk-modeling.inner_features_call": "InnerFeaturesCallback",
        }

        coro_list = [
            self.get_queue(queue_name) for queue_name in queue_callback_mapping
        ]
        queues = asyncio.gather(*coro_list)
        for queue in await queues:
            callback_name = queue_callback_mapping[queue.name]
            try:
                await queue.consume(self._initialized_callbacks[callback_name].callback)
            except Exception as e:
                logger.exception("[LISTEN] " + str(e))


async def main(consumer):
    await consumer.mq_init()
    await consumer.consume()


if __name__ == "__main__":
    consumer = Consumer(
        name="Consumer",
        callbacks=[
            InnerFeaturesCallback,
        ],
    )

    loop = asyncio.get_event_loop()
    try:
        loop.create_task(main(consumer))
        loop.run_forever()
    except Exception as e:
        logger.exception("[LISTEN] " + str(e))
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(0)
