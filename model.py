import json
import random
import time
from datetime import datetime

import asyncio
import aio_pika
from aio_pika import Message, DeliveryMode
from aio_pika.pool import Pool

from comlog import logger


class RabbitMQ:
    def __init__(self):
        self._inited = False

    async def get_connection(self):
        return await aio_pika.connect_robust("amqp://guest:guest@localhost/")

    async def get_channel(self):
        async with self.connection_pool.acquire() as connection:
            return await connection.channel()

    async def mq_init(self) -> None:
        if self._inited:
            return
        logger.info("[MODEL] Initing RabbitMQ connection and channel pools...")
        self.connection_pool = Pool(self.get_connection, max_size=2)  # 2
        self.channel_pool = Pool(self.get_channel, max_size=2)  # 10
        self._inited = True

    async def publish(self, msg: str, route_key: str) -> int:
        """here, expect route_key to always be risk-modeling.inner_features_call"""

        await self.mq_init()
        async with self.channel_pool.acquire() as channel:
            if channel.is_closed:
                logger.warning("aiormq channel {!r} closed".format(channel))
                # attempt to restart pool after channel closure
                self._inited = False
                return 1
            queue = await channel.declare_queue(
                "risk-modeling.inner_features_call", durable=True
            )
            exchange = await channel.declare_exchange(
                "exchange.risk-modeling", type="topic", durable=True
            )
            await queue.bind(exchange, routing_key="risk-modeling.inner_features_call")

            # randomly close channel (to reproduce the error)
            if random.random() < 0.08:
                logger.info("[HAHAHA] Randomly closing channel...")
                await channel._channel.close()
                return 1

            await channel.set_qos(prefetch_count=10)  # 10
            exchange = await channel.get_exchange("exchange.risk-modeling")
            await exchange.publish(
                Message(msg.encode(), delivery_mode=DeliveryMode.NOT_PERSISTENT),
                route_key,
            )
            return 0


async def main() -> None:
    LONG_STRINGS = [
        "MANUFACTURING_AND_ELECTRONICS",
        "APPLE STRAWBERRY BANANA",
        "TOGETHER WE CRY THE SCRIPT",
        "NEW BALANCE WATER BOTTLE",
    ]
    rmq = RabbitMQ()
    await rmq.mq_init()

    n = 5  # controls the length/size of the individual messages
    num_messages = 35
    for i in range(num_messages):
        msg = json.dumps(
            {
                "index": i,
                "score_timestamp": str(datetime.now()),
                **{f"f{x:03d}": random.random() for x in range(n)},
                **{f"f{x:03d}": random.choice(LONG_STRINGS) for x in range(n, 2 * n)},
            }
        )

        # Sending the message
        # print("Is channel closed?", channel.is_closed)
        max_retries = 2
        for tc in range(max_retries + 1):
            if tc > 0:
                logger.info(
                    "Retrying rabbitmq publishing after failure... Retry count {}".format(
                        tc
                    )
                )

            exit_code = await rmq.publish(
                msg, route_key="risk-modeling.inner_features_call"
            )
            if not exit_code:
                # published message successfully
                logger.info(f"[MODEL] published message {i}")
                break
            else:
                logger.info(f"[MODEL] message {i} failed")
        else:
            logger.error(
                "Rabbitmq publish failure for xxx after {} retries!".format(max_retries)
            )

        # delay some time before sending next msg
        time.sleep(random.uniform(0.02, 0.15))


if __name__ == "__main__":
    asyncio.run(main())
