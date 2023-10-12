
from ETS_CookBook import ETS_CookBook as cook

try:
    from pLAtYpus_TNO import solver
except ModuleNotFoundError:
    import solver

try:
    from pLAtYpus_TNO import maps
except ModuleNotFoundError:
    import maps


def make_all_outputs(parameters):
    solver.get_all_evolutions_and_plots(parameters)
    maps.make_long_term_average_tables(parameters)
    maps.make_area_maps(parameters)


if __name__ == '__main__':
    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)
    make_all_outputs(parameters)
