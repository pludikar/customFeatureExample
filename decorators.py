import logging
import re
import adsk.core, adsk.fusion
from typing import ClassVar
from dataclasses import dataclass
import pprint
from functools import wraps

pp = pprint.PrettyPrinter()

logger = logging.getLogger('customCove.decorators')
logger.setLevel(logging.DEBUG)
_app = adsk.core.Application.get()
des: adsk.fusion.Design = _app.activeProduct

@dataclass
class HandlerContext():
    handler: adsk.core.Base
    event: adsk.core.Event


@dataclass
class HandlerCollection(HandlerContext):
    '''
    class to keep event handlers persistent
    It's not apparent if it's possible to figure which event each handler is attached to
    If you want to remove a handler selectively, you need both event and handler together.
    '''
    handlers: ClassVar = {}
    groupId: str = 'default'
    
    def __post_init__(self):
        try:
            HandlerCollection.handlers.setdefault(self.groupId, []).append(HandlerContext(self.handler, self.event))
        except KeyError:
            HandlerCollection.handlers[self.groupId] = [HandlerContext(self.event, self.handler)]

    @classmethod
    def remove(cls, groupId=None):
        '''
        Simple remove of group key and its values - python GC will clean up any orphaned handlers
        If parameter is None then do a complete HandlerCollection reset
        '''
        if not groupId:
            cls.handlers = None
            return
        try:
            del cls.handlers[groupId]
        except KeyError:
            return

    # TODO - add selective eventHandler removal - might be more trouble than it's worth

# Decorator to add eventHandler
def eventHandler(handler_cls=adsk.core.Base):
    '''
    handler_cls is a subClass of EventHandler base class, which is not explicitly available.
    It must be user provided, and thus you can't declare the handler_cls to be of EventHandler type 
    EventHandler Classes such as CommandCreatedEventHandler, or MouseEventHandler etc. are provided to ensure type safety
    '''
    def decoratorWrapper(notify_method):
        @wraps(notify_method)  #spoofs wrapped method so that __name__, __doc__ (ie docstring) etc. behaves like it came from the method that is being wrapped.   
        def handlerWrapper( *handler_args, event=adsk.core.Event, groupId:str='default',**handler_kwargs):
            '''When called returns instantiated _Handler 
                - assumes that the method being wrapped comes from an instantiated Class method
                - inherently passes the "self" argument, if called method is in an instantiated class  
                - kwarg "event" throws an error if not provided '''

            logger.debug(f'notify method created: {notify_method.__name__}')

            try:

                class _Handler(handler_cls):

                    def __init__(self):
                        self._disabled = False
                        self._disabledOnce = False
                        super().__init__()

                    def disableOnce(self):
                        self._disabledOnce = True
                        logger.debug(f'{notify_method.__name__} handler disabledOnce set to {self._disabledOnce}')

                    def enable(self):
                        self._disabled = False

                    def disable(self):
                        self._disabled = True

                    def notify( self, eventArgs):
                        try:
                            logger.debug(f'{notify_method.__name__} handler notified: {eventArgs.firingEvent.name}')
                            logger.debug(f'{notify_method.__name__} Once is {"Disabled".upper() if not self._disabledOnce else "Enabled".upper()} ')
                            if self._disabledOnce or self._disabled:
                                self._disabledOnce = False
                                logger.debug(f'{notify_method.__name__} handler disabledOnce {self._disabledOnce}')
                                return
                            notify_method(*handler_args, eventArgs)  #notify_method_self and eventArgs come from the parent scope
                        except Exception as e:
                            print(e)
                            logger.exception(f'{eventArgs.firingEvent.name} error termination')
                h = _Handler() #instantiates handler with the arguments provided by the decorator
                event.add(h)  #this is where the handler is added to the event
                # HandlerCollection.handlers.append(HandlerCollection(h, event))
                HandlerCollection(groupId=groupId, handler=h, event=event)
                logger.debug(f'\n{pp.pformat(HandlerCollection.handlers)}')
                # adds to class handlers list, needs to be persistent otherwise GC will remove the handler
                # - deleting handlers (if necessary) will ensure that garbage collection will happen.
            except Exception as e:
                print(e)
                logger.exception(f'handler creation error')
            return h
        return handlerWrapper
    return decoratorWrapper


def timelineMarkers(func):
    ''' logs timeline marker before and after eventHandler call'''
    # func = decoratorArgs[0]
    @wraps(func)
    def inner(*args, **kwargs):
        global _app
        des: adsk.fusion.Design = _app.activeProduct

        logger.debug(f'Start - {func.__name__} = {des.timeline.markerPosition}')
        r = func(*args, **kwargs)
        logger.debug(f'End - {func.__name__} = {des.timeline.markerPosition}')

        return r
    return inner

# def disable_compute_event(func, event_handler):
#     @wraps(func)
#     def inner(*args, **kwargs):
#         global _compute_handler
#         event_handler.disable()
#         result = func()
#         event_handler.enable()
#         return result
#     return inner
