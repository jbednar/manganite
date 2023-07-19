import sys
from io import BytesIO

import panel as pn
import pandas as pd


__version__ = '0.0.3'

CSS_FIX = """
#sidebar { background-color: #eee; }
.grid-stack-item-content > * { margin: 0 !important; }
.xterm .xterm-viewport { width: auto !important; }
"""


class Manganite:
    _nb_instance = None
    _server_instances = {}


    def __init__(self, *args, **kwargs):
        title = kwargs.pop('title', None) or 'Manganite App'
        description = kwargs.pop('description', None)

        pn.extension(
            'terminal', 'gridstack', 'tabulator', 'plotly', 'mathjax', *args,
            raw_css=[CSS_FIX], sizing_mode='stretch_width', **kwargs)

        if pn.state.curdoc: # shared environment
            Manganite._server_instances[pn.state.curdoc] = self
        else: # running in JupyterLab
            Manganite._nb_instance = self

        self._init_terminal()
        self._optimizer_button = pn.widgets.Button(name='▶ Run', width=80)
        self._optimizer_result = None
        self.optimizer_done = pn.widgets.BooleanStatus(value=False)

        self._layout = {'Description': pn.Column()}

        if description is not None:
            self._layout['Description'].append(pn.pane.Markdown(description))

        self._tabs = pn.Tabs(
            ('Description', self._layout['Description']),
            dynamic=True)
        
        self._header = pn.FlexBox(justify_content='end')

        self._template = pn.template.MaterialTemplate(
            header=[self._header],
            header_background='#000228',
            sidebar=['## Log', self._optimizer_terminal],
            main=[self._tabs],
            sidebar_width=400,
            site='CAVE Lab&nbsp;',
            title=title
        ).servable()


    def _init_terminal(self):
        terminal_options = {}
        theme = pn.state.session_args.get('theme')
        if theme is None or theme[0] != 'dark':
            terminal_options['theme'] = {
                'background': '#fff',
                'foreground': '#000'
            }

        self._optimizer_terminal = pn.widgets.Terminal(
            sizing_mode='stretch_both',
            write_to_console=True,
            options=terminal_options)
        
    
    def get_tab(self, name):
        if name not in self._layout:
            self._layout[name] = pn.GridBox(ncols=2)
            self._tabs.append((name, self._layout[name]))
        
        return self._layout[name]
    

    def get_header(self):
        return self._header


    @classmethod
    def get_instance(cls):
        if pn.state.curdoc:
            if pn.state.curdoc not in cls._server_instances:
                if cls._nb_instance and pn.state.curdoc is cls._nb_instance._template.server_doc():
                    cls._server_instances[pn.state.curdoc] = cls._nb_instance
            return cls._server_instances[pn.state.curdoc]
        return cls._nb_instance


def init(*args, **kwargs):
    mnn = Manganite(*args, **kwargs)
    return mnn


def get_template():
    return Manganite.get_instance()._template


def get_layout():
    return Manganite.get_instance()._layout


def create_upload_handler(transform=None):
    def callback(target, event):
        if event.new is not None:
            df = pd.read_csv(BytesIO(event.new))
            if transform is not None:
                df = transform(df)
            target.value = df
    return callback


def on_optimize(handler, cb=None):
    mnn = Manganite.get_instance()
    def wrapped_handler(*events):
        sys.stdout = mnn._optimizer_terminal
        sys.stderr = mnn._optimizer_terminal
        mnn._optimizer_terminal.clear()
        mnn.optimizer_done.value = False
        try:
            mnn._optimizer_result = handler()
            mnn.optimizer_done.value = True
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

        if cb is not None:
            cb()

    mnn._optimizer_button.on_click(wrapped_handler)


def get_result():
    mnn = Manganite.get_instance()
    return mnn._optimizer_result


def load_ipython_extension(ipython):
    from .magics import ManganiteMagics
    init()
    ipython.register_magics(ManganiteMagics)


def _jupyter_server_extension_points():
    return [{
        'module': 'manganite.jupyter'
    }]
