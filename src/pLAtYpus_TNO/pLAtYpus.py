
import datetime

from ETS_CookBook import ETS_CookBook as cook

try:
    from pLAtYpus_TNO import solver
except ModuleNotFoundError:
    import solver

try:
    from pLAtYpus_TNO import maps
except ModuleNotFoundError:
    import maps

try:
    from pLAtYpus_TNO import survey_to_pLAtYpus
except ModuleNotFoundError:
    import survey_to_pLAtYpus

try:
    from pLAtYpus_TNO import process_survey_data
except ModuleNotFoundError:
    import process_survey_data


if __name__ == '__main__':
    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)
    cook.check_if_folder_exists('output')
    cook.check_if_folder_exists('input')

    start = datetime.datetime.now()
    stakeholders = parameters['pLAtYpus']['stakeholders']
    for stakeholder in stakeholders:
        topic_answers, topic_dataframe = process_survey_data.read_source_sheet(
            stakeholder, parameters
        )
        print(stakeholder)
        process_survey_data.write_full_processed_data(
            parameters, topic_answers, topic_dataframe,
            stakeholder
        )
    end = datetime.datetime.now()
    print((end-start).total_seconds())

    start = datetime.datetime.now()
    survey_to_pLAtYpus.get_survey_product_values(parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())

    start = datetime.datetime.now()
    solver.get_all_evolutions_and_plots(parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())

    start = datetime.datetime.now()
    maps.make_long_term_average_tables(parameters)
    maps.make_area_maps(parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())
