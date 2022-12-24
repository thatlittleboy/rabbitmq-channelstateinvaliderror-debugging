# rabbitmq-channelstateinvaliderror-debugging

**Background**: Facing ChannelStateInvalidError errors in production.

```python
ChannelInvalidStateError('writer is None',)
Traceback:
  File '/app/modeling_service/model/base.py', line 245, in process
    await self.do_inner_features_call(input_data, res)

  File '/app/modeling_service/util/logging/decorators.py', line 16, in do_f
    ret = await f(*args, **kwargs)

  File '/app/modeling_service/model/base.py', line 226, in do_inner_features_call
    await self.inner_features_call_rabbitmq.publish(json.dumps(msg), route_key)

  File '/app/modeling_service/util/rabbitmq.py', line 32, in publish
    await channel.set_qos(10)

  File '/usr/local/lib/python3.6/site-packages/aio_pika/robust_channel.py', line 110, in set_qos
    timeout=timeout,

  File '/usr/local/lib/python3.6/site-packages/aio_pika/channel.py', line 379, in set_qos
    timeout=timeout,

  File '/usr/local/lib/python3.6/asyncio/tasks.py', line 339, in wait_for
    return (yield from fut)

  File '/usr/local/lib/python3.6/site-packages/aiormq/channel.py', line 563, in basic_qos
    timeout=timeout,

  File '/usr/local/lib/python3.6/site-packages/aiormq/base.py', line 168, in wrap
    return await self.create_task(func(self, *args, **kwargs))

  File '/usr/local/lib/python3.6/site-packages/aiormq/base.py', line 25, in __inner
    return await self.task

  File '/usr/local/lib/python3.6/site-packages/aiormq/channel.py', line 121, in rpc
    raise ChannelInvalidStateError('writer is None')
```

This repo is an attempt to reproduce that error in a minimal fashion (and a good chance for me to learn rabbitmq from scratch), then debugging the error, then fixing the error.  
Also meant as a backup reference guide for myself, how to set up a consumer-producer pair.

In production, we're using `aio_pika==6.8.0` hence the pin to that version in the requirements.

## Getting started

One time setup on MacOS

```sh
brew install rabbitmq
brew services start rabbitmq  # launch daemon
```

Then python environment:

```sh
init_venv  # initialize a python venv (py 3.7)
avenv  # activate the venv
pip install -r requirements.txt
```

Read https://aio-pika.readthedocs.io/en/6.8.0/rabbitmq-tutorial/1-introduction.html

## Things I learnt:

- **Steps**: `aio_pika.connect_robust()` to get a connection, then `connection.get_channel()` to get a channel, then finally declare a queue `channel.get_queue()`.
- `basic.qos(prefetch_count=1)` method tells RabbitMQ not to give more than one message to a worker at a time (only dispatch after the worker has acknowledged the previous task).
- producers send messages to an exchange; the exchange is responsible for dealing with the messages (which queues to send to - this relationship is called a binding); consumers consume messages from the queue.
-

## Reproducing the ChannelStateInvalidError and Debugging

Project Structure:

- `model.py`: the model service producing the messages
- `listener.py`: the inner features service listening to the queue, consuming the messages and dumping data to db.

Details:

- Open two terminal windows, run `python model.py` (producer) and `python listener.py` (consumer).
- The way I'm reproducing is by manually triggering the channel closure (hooking into the underlying `aiormq` Channel, not the `aio_pika` Channel wrapper class) -- see `model.py` file.
- Then the solution is to add a retry mechanism + manually set the `_inited` back to False again, so that the ChannelPool is re-initialized and we get some fresh Channels in the Pool (otherwise it will just keep recycling the old already-closed channels).
