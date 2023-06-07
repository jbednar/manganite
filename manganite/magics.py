import datetime
from dataclasses import dataclass, field
from shlex import split
from typing import Callable
from warnings import warn

import panel as pn
import param
from pandas import DataFrame
from IPython.core.magic import Magics, magics_class, cell_magic, needs_local_scope
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring


@dataclass
class RerunnableCell():
    deps: list = field(default_factory=list)
    pane: pn.viewable.Viewable = None
    rerun: Callable = None

    def display_if_defined(self, local_ns, widget_name, widget_title, stage, coords):
        from manganite import get_layout

        if widget_name.isidentifier() and widget_name in local_ns and len(coords):
            widget = local_ns[widget_name]
            if isinstance(widget, int):
                widget = pn.widgets.IntInput(value=widget)
                local_ns[widget_name] = widget
            elif isinstance(widget, float):
                widget = pn.widgets.FloatInput(value=widget)
                local_ns[widget_name] = widget
            elif isinstance(widget, DataFrame):
                widget = pn.widgets.Tabulator(value=widget)
                local_ns[widget_name] = widget
            elif isinstance(widget, datetime.datetime):
                widget = pn.widgets.DatetimePicker(value=widget)
                local_ns[widget_name] = widget
            elif isinstance(widget, tuple) and len(widget) == 2 and all(isinstance(el, datetime.datetime) for el in widget):
                widget = pn.widgets.DatetimeRangePicker(value=widget)
                local_ns[widget_name] = widget

            if self.pane is None:
                y, x, w = coords
                self.pane = pn.panel(widget)

                grid = get_layout()[stage]
                grid[y, x:x+w] = pn.Column(
                    pn.pane.Markdown('### {}'.format(widget_title or widget_name)), self.pane, height=300)
                grid.height = grid.nrows * 350
            else:
                self.pane.object = widget


@magics_class
class ManganiteMagics(Magics):
    _unwrappable_types = (
        pn.widgets.IntInput,
        pn.widgets.FloatInput,
        pn.widgets.Tabulator,
        pn.widgets.DatetimePicker,
        pn.widgets.DatetimeRangePicker)


    def __init__(self, *args, **kwargs):
        super(ManganiteMagics, self).__init__(*args, **kwargs)
        self._cells = {}
        self._result_cells = {}


    def unwrap_widgets(self, local_ns):
        wrapper_mapping = {}
        for variable in self._cells.keys():
            if not isinstance(local_ns.get(variable, None), self._unwrappable_types):
                continue
            wrapper_mapping[variable] = local_ns[variable]
            local_ns[variable] = wrapper_mapping[variable].value

        return wrapper_mapping


    def rewrap_widgets(self, local_ns, wrapper_mapping):
        for variable in wrapper_mapping.keys():
            # reassigned to some other value?
            if not isinstance(local_ns.get(variable, None), type(wrapper_mapping[variable].value)):
                continue
            if wrapper_mapping[variable].value is not local_ns[variable]:
                wrapper_mapping[variable].value = local_ns[variable]
            local_ns[variable] = wrapper_mapping[variable]


    def make_rerunnable(self, stage, args, cell_source, local_ns):
        if args.name.isidentifier() and args.name in self._cells:
            warn('Widget {} already defined, overwriting'.format(args.name))
            # TODO: unwatch

        if hasattr(args, 'deps'):
            for dep in args.deps or []:
                if dep not in local_ns:
                    raise NameError('Dependency {} is not in the global scope'.format(dep))
                if not issubclass(local_ns[dep].__class__, param.Parameterized):
                    raise TypeError('Dependency {} is not a watchable value'.format(dep))

        cell = self._cells.setdefault(args.name, RerunnableCell(deps=args.deps if hasattr(args, 'deps') and args.deps else []))

        def rerun(*events):
            wrapper_mapping = self.unwrap_widgets(local_ns)
            exec(cell_source, local_ns, local_ns)
            self.rewrap_widgets(local_ns, wrapper_mapping)

            cell.display_if_defined(local_ns, args.name, args.header, stage, args.display)

        cell.rerun = rerun
        return cell


    @magic_arguments()
    @argument('name',
              type=str,
              help='Variable to wrap in a widget or a unique description string')
    @argument('--header', '-h',
              type=str,
              help='Title to display above the widget')
    @argument('--display', '-d',
              type=int, nargs=3,
              help='Grid coordinates and width of the widget',
              metavar=('Y', 'X', 'W'))
    @argument('--recalc-on', '-r',
              dest='deps',
              type=str, nargs='+',
              help='List of variables which should trigger a cell rerun on change')
    @needs_local_scope
    @cell_magic
    def mnn_input(self, arg_line, cell_source, local_ns):
        # args = parse_argstring(ManganiteMagics.mnn_input, arg_line)
        args = ManganiteMagics.mnn_input.parser.parse_args(split(arg_line))

        cell = self.make_rerunnable('inputs', args, cell_source, local_ns)
        for dep in args.deps or []:
            local_ns[dep].param.watch(cell.rerun, ['value'])

        cell.rerun()


    @magic_arguments()
    @argument('name',
              type=str,
              help='Variable to wrap in a widget or a unique description string')
    @argument('--header', '-h',
              type=str,
              help='Title to display above the widget')
    @argument('--display', '-d',
              type=int, nargs=3,
              help='Grid coordinates and width of the widget',
              metavar=('Y', 'X', 'W'))
    @needs_local_scope
    @cell_magic
    def mnn_result(self, arg_line, cell_source, local_ns):
        # args = parse_argstring(ManganiteMagics.mnn_result, arg_line)
        args = ManganiteMagics.mnn_result.parser.parse_args(split(arg_line))
        cell = self.make_rerunnable('results', args, cell_source, local_ns)

        self._result_cells.setdefault(args.name, cell)


    @needs_local_scope
    @cell_magic
    def mnn_model(self, arg_line, cell_source, local_ns):
        from manganite import on_optimize

        def run_results():
            for cell in self._result_cells.values():
                cell.rerun()

        def run_model():
            exec(cell_source, local_ns, local_ns)

        on_optimize(run_model, run_results)
