import shutil
import tempfile
import weakref

import panel as pn

from .grid import Grid

__version__ = '0.0.3'

CSS_FIX = """
#sidebar { background-color: #fafafa; }
#sidebar > .mdc-drawer__content > .mdc-list { box-sizing: border-box; height: 100%; }
"""

SIDEBAR_OUTER_WIDTH = 400
SIDEBAR_INNER_WIDTH = SIDEBAR_OUTER_WIDTH - 10 - 1

pn.extension(
    'terminal', 'gridstack', 'tabulator', 'plotly', 'mathjax',
    raw_css=[CSS_FIX], sizing_mode='stretch_width')


class Manganite:
    _nb_instance = None
    _server_instances = {}


    def __init__(self, *args, **kwargs):
        title = kwargs.pop('title', None) or 'Manganite App'
        description = kwargs.pop('description', None)

        if pn.state.curdoc: # shared environment
            Manganite._server_instances[pn.state.curdoc] = self
        else: # running in JupyterLab
            Manganite._nb_instance = self

        self._upload_dir = tempfile.mkdtemp(prefix='mnn_uploads__')
        self._finalizer = weakref.finalize(self, shutil.rmtree, self._upload_dir)

        self._init_terminal()
        self._optimizer_button = pn.widgets.Button(name='▶ Run', width=80)
        self._optimizer_result = None
        self.optimizer_done = pn.widgets.BooleanStatus(value=False)

        self._layout = {'Description': pn.Column()}

        if description is not None:
            self._layout['Description'].append(pn.pane.Markdown(description))

        self._tabs = pn.Tabs(('Description', self._layout['Description']))
        
        self._header = pn.FlexBox(justify_content='end')
        self._sidebar = pn.FlexBox(
            flex_direction='column',
            flex_wrap='nowrap',
            width=SIDEBAR_INNER_WIDTH) # explicit width for proper initial terminal size
        self._sidebar.append('## Log')
        self._sidebar.append(self._optimizer_terminal)

        self._template = pn.template.MaterialTemplate(
            collapsed_sidebar=True,
            header=[self._header],
            header_background='#000228',
            sidebar=[self._sidebar],
            main=[self._tabs],
            sidebar_width=SIDEBAR_OUTER_WIDTH,
            title=title
        ).servable()


    def _init_terminal(self):
        terminal_options = {'fontSize': 14}
        theme = pn.state.session_args.get('theme')
        if theme is None or theme[0] != 'dark':
            terminal_options['theme'] = {
                'background': '#fafafa',
                'foreground': '#000'
            }

        self._optimizer_terminal = pn.widgets.Terminal(
            write_to_console=True,
            options=terminal_options,
            stylesheets=['.terminal-container { width: 100% !important; } .xterm .xterm-viewport { width: auto !important; }'])
        
    
    def get_tab(self, name):
        if name not in self._layout:
            self._layout[name] = Grid()
            self._tabs.append((name, self._layout[name]))
        
        return self._layout[name]
    

    def get_header(self):
        return self._header
    

    def get_upload_dir(self):
        return self._upload_dir


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


def load_ipython_extension(ipython):
    from .magics import ManganiteMagics
    init()
    ipython.register_magics(ManganiteMagics)


def _jupyter_server_extension_points():
    return [{
        'module': 'manganite.jupyter'
    }]
