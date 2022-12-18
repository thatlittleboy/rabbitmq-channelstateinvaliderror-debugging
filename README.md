# rabbitmq-channelstateinvaliderror-debugging

**Background**: Facing ChannelStateInvalidError errors in production. This repo is an attempt to reproduce that error in a minimal fashion (and a good chance for me to learn rabbitmq from scratch), then debugging the error, then fixing the error.  
Also meant as a backup reference guide for myself, how to set up a consumer-producer pair.

In production, we're using `aio_pika==6.8.0` hence the pin to that version in the requirements.

## Getting started

One time setup

```sh
brew install rabbitmq
brew services start rabbitmq  # launch daemon
```

Read https://aio-pika.readthedocs.io/en/6.8.0/rabbitmq-tutorial/1-introduction.html

## Things I learnt:

- **Steps**: `aio_pika.connect_robust()` to get a connection, then `connection.get_channel()` to get a channel, then finally declare a queue `channel.get_queue()`.
- `basic.qos(prefetch_count=1)` method tells RabbitMQ not to give more than one message to a worker at a time (only dispatch after the worker has acknowledged the previous task).
- producers send messages to an exchange; the exchange is responsible for dealing with the messages (which queues to send to - this relationship is called a binding); consumers consume messages from the queue.
-

## Reproducing the ChannelStateInvalidError and Debugging

Structure:

- `model.py`: the model service producing the messages
- `listener.py`: the inner features service listening to the queue, consuming the messages and dumping data to db.

- Open two terminal windows, run `python model.py` (producer) and `python listener.py` (consumer).
- The way I'm reproducing is by manually triggering the channel closure (hooking into the underlying `aiormq` Channel, not the `aio_pika` Channel wrapper class) -- see `model.py` file.
- Then the solution is to add a retry mechanism + manually set the `_inited` back to False again, so that the ChannelPool is re-initialized and we get some fresh Channels in the Pool (otherwise it will just keep recycling the old already-closed channels).
