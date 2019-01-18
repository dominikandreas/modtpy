from collections import OrderedDict
import click
import time
from modtpy.api.modt import ModT
from modtpy.api.usb import Mode


def _ensure_connected(callback_function, required_mode=None):
    def wrapper(*args, **kwargs):
        i = 0
        modt = ModT()
        while modt.mode == Mode.DISCONNECTED:
            print("\rWaiting for Mod-T connection " + ("." * i), end=" ")
            time.sleep(.5)
            i = (i + 1) % 4
        if required_mode is not None and modt.mode != required_mode:
            if modt.mode == Mode.DFU:
                print("printer is currently in dfu mode. you can put it back into operating mode by restarting it")
                exit()
            elif modt.mode == Mode.OPERATE:
                modt.enter_dfu(wait_for_dfu=True)

        return callback_function(*args, modt=modt, **kwargs)
    wrapper.__name__ = callback_function.__name__

    return wrapper


def ensure_connected(required_mode_or_function=None):
    if callable(required_mode_or_function):
        f = required_mode_or_function
        return _ensure_connected(f)
    else:
        def __wrapper__(f_):
            return _ensure_connected(f_, required_mode=required_mode_or_function)

        return __wrapper__


def get_user_input(prompt, validate=lambda c: c is not None, type=None, invalid_reason=lambda s: ""):
    while True:
        choice = click.prompt(prompt, type=type)
        if not validate(choice):
            print("Choice is not valid." + invalid_reason(choice))
        else:
            return choice


def get_user_choice(choices, prompt="Please select:", item_to_str=lambda i: str(i)):
    choices = choices if isinstance(choices, dict) else OrderedDict((i, c) for i, c in enumerate(choices))
    prompt = prompt + "\n" + "\n".join(["\t%s: %s" % (k, item_to_str(v)) for k, v in choices.items()])
    i = get_user_input(prompt=prompt + "\nChoice", validate=lambda c: c in choices, type=int)
    return choices[i]
