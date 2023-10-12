
import pandas as pd
import sqlite3
from ETS_CookBook import ETS_CookBook as cook
import math
import shutil


def get_component_values(
        stakeholder, component, product, country, parameters):
    '''
    Gets the values for a given componentfor a given product and country from
    a survey by collecting
    answers to the questions that are relevant to this component (and
    taking the answers that would either push the stakeholder
    to adopt or leave).
    '''

    survey_parameters = parameters['survey']

    survey_data_folder = survey_parameters['data']['output']['output_folder']
    survey_data_file_name = (
        survey_parameters['data']['output']['database_file_name']
    )
    survey_data_file = f'{survey_data_folder}/{survey_data_file_name}'

    survey_component_parameters = (
        survey_parameters['products'][stakeholder][product][component]
    )
    top_answer_levels_list = survey_component_parameters['top_answer_levels']
    bottom_answer_levels_list = (
        survey_component_parameters['bottom_answer_levels']
    )
    answer_lengths_list = survey_component_parameters['answer_lengths']
    adopt_are_top_list = survey_component_parameters['adopt_are_top']
    prefixes = survey_component_parameters['prefixes']
    midfixes = survey_component_parameters['midfixes']
    suffixes = survey_component_parameters['suffixes']
    total_shifts_from_bottom_list = (
        survey_component_parameters['total_shifts_from_bottom']
    )

    adopt_answers = 0
    leave_answers = 0
    total_answers = 0

    with sqlite3.connect(survey_data_file) as database_connection:

        for (
            prefix, midfix, suffix_list, top_answer_levels,
            bottom_answer_levels, answer_lengths, adopt_are_top,
            total_shifts_from_bottom
            ) in zip(
                        prefixes, midfixes, suffixes, top_answer_levels_list,
                        bottom_answer_levels_list, answer_lengths_list,
                        adopt_are_top_list, total_shifts_from_bottom_list
                    ):
            for (
                suffix, top_answer_level, bottom_answer_level,
                answer_length, adopt_is_top, total_shift_from_bottom
                ) in zip(
                        suffix_list, top_answer_levels, bottom_answer_levels,
                        answer_lengths, adopt_are_top, total_shifts_from_bottom
                    ):
                survey_code = f'{stakeholder}_{prefix}{midfix}{suffix}'
                sql_query = cook.read_query_generator(
                    country, survey_code, '', '', ''
                )

                parameter_data = pd.read_sql(
                    sql_query, con=database_connection
                )
                bottom_answers = (
                    sum(parameter_data.values[0:bottom_answer_level])[0]
                )
                top_answers = sum(
                    parameter_data.values[
                        answer_length-top_answer_level:answer_length
                        ]
                )[0]
                total_answers += (
                    parameter_data.values[-(1+total_shift_from_bottom)][0]
                )

                if adopt_is_top:
                    adopt_answers += top_answers
                    leave_answers += bottom_answers
                else:
                    adopt_answers += bottom_answers
                    leave_answers += top_answers

    adopt_value = adopt_answers/total_answers
    leave_value = leave_answers/total_answers

    return adopt_value, leave_value


def get_survey_product_values(parameters):
    '''
    Gets all product values (listed and defined in the parameters file)
    from the survey.
    '''

    stakeholders = parameters['pLAtYpus']['stakeholders']
    countries = parameters['survey']['countries']
    products = list(parameters['products'].keys())
    survey_index_tuples = (
        [
            (country, product, stakeholder, component)
            for country in countries
            for product in products
            for stakeholder in stakeholders
            for component in (
                    parameters['survey']['products'][stakeholder][product]
            )
        ]
    )
    survey_index = (
        pd.MultiIndex.from_tuples(
            survey_index_tuples,
            names=['Country', 'Product', 'Stakeholder', 'Component']
            )
    )
    survey_scores_actions = parameters['survey']['survey_scores_actions']
    survey_dataframe = (
        pd.DataFrame(columns=survey_scores_actions, index=survey_index)
    )

    for stakeholder in stakeholders:
        file_parameters = parameters['files']
        output_folder = file_parameters['output_folder']
        groupfile_name = file_parameters['groupfile_name']

        survey_topics_table_name = file_parameters['survey_topics_table_name']

        components = {}
        for product in products:
            components[product] = (
                parameters['survey']['products'][stakeholder][product]
            )

        for country in countries:
            for product in products:
                for component in components[product]:
                    adopt_value, leave_value = get_component_values(
                        stakeholder,
                        component, product, country, parameters
                    )
                    survey_dataframe.loc[
                        (country, product, stakeholder, component)] = (
                        [adopt_value, leave_value]
                    )

        get_relational_values_from_survey(stakeholder, parameters)

        relations_deviations_dataframe = (
            get_relationship_deviations(stakeholder, parameters)
        )

        partners = parameters['survey']['relations'][stakeholder]['partners']
        for country in countries:
            for partner in partners:
                for product in products:
                    component = f'relation_score_{partner}'
                    adopt_value = (
                        relations_deviations_dataframe.loc[
                            (country, product, partner)]['Relation score']
                    )
                    leave_value = 1 - adopt_value
                    survey_dataframe.at[
                        (country, product, stakeholder, component),
                        'Adopt'] = (
                            adopt_value
                        )
                    survey_dataframe.at[
                        (country, product, stakeholder, component),
                        'Leave'] = (
                            leave_value
                        )

                    # We also need a survey answer of 1 (for social norm, where
                    # the score is given by the adoption of a given partner)
                    survey_dataframe.at[
                        (country, product, stakeholder, 'one'), 'Adopt'] = 1
                    survey_dataframe.at[
                        (country, product, stakeholder, 'one'), 'Leave'] = 1
    survey_dataframe = survey_dataframe.sort_index()
    cook.save_dataframe(
        survey_dataframe, survey_topics_table_name, groupfile_name,
        output_folder, parameters
    )
    get_intention_weights(parameters)
    pLAtYpus_parameters = parameters['pLAtYpus']
    common_initial_yes = pLAtYpus_parameters['initial_yes']

    for product in products:
        initial_yes = pd.DataFrame(columns=stakeholders, index=countries)
        initial_yes.index.name = 'Country'
        for country in countries:
            initial_yes.loc[country] = common_initial_yes

        cook.save_dataframe(
            initial_yes, f'Initial Yes {product}', groupfile_name,
            output_folder, parameters
        )
    # Finally, we make a copy of the database for resets in the GREAT tool
    # This is a version with only the survey data
    groupfile_name_only_survey = file_parameters['groupfile_name_only_survey']
    database_file = f'{output_folder}/{groupfile_name}.sqlite3'
    database_file_for_resets = (
        f'{output_folder}/{groupfile_name_only_survey}.sqlite3'
    )
    shutil.copy(database_file, database_file_for_resets)


def component_adopt_leave(component, product, country, parameters):
    '''
    Reads the component adopt and leave values for a given product and country.
    '''

    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    survey_topics_table_name = file_parameters['survey_topics_table_name']
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    with sqlite3.connect(source_database) as database_connection:
        sql_query = cook.read_query_generator(
                        '*', survey_topics_table_name,
                        ['Product', 'Country', 'Component'],
                        ['=', '='],
                        [f'"{product}"', f'"{country}"', f'"{component}"']
                    )

        adopt_leave_values = pd.read_sql(
            sql_query, con=database_connection
        )
    adopt = adopt_leave_values['Adopt'][0]
    leave = adopt_leave_values['Leave'][0]

    return adopt, leave


def get_relational_values_from_survey(stakeholder, parameters):
    '''
    Gets perceived and desired relational models for various products/services
    '''

    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    survey_parameters = parameters['survey']
    countries = survey_parameters['countries']

    survey_data_folder = survey_parameters['data']['output']['output_folder']
    survey_data_file_name = (
        survey_parameters['data']['output']['database_file_name']
    )
    survey_data_file = f'{survey_data_folder}/{survey_data_file_name}'

    product_list = parameters['products']
    relation_definition_parameters = (
        survey_parameters['relation_definitions']
    )
    # relation_names = (
    #     relation_definition_parameters['relation_names']
    # )
    relation_types = (
        relation_definition_parameters['relation_types']
    )
    table_name_root = (
        relation_definition_parameters['table_name']
    )

    stakeholder_relations_parameters = (
        survey_parameters['relations'][stakeholder]
    )
    partners = stakeholder_relations_parameters['partners']

    relations_dataframe_index_tuples = (
        [
            (country, relation_type)
            for country in countries
            for relation_type in relation_types

        ]
    )

    relations_dataframe_index = (
        pd.MultiIndex.from_tuples(
            relations_dataframe_index_tuples,
            names=['Country', 'Relation_type']
        )
    )

    with sqlite3.connect(survey_data_file) as database_connection:
        for product in product_list:
            product_parameters = (
                survey_parameters['relations'][stakeholder][product]
            )
            perceived_codes = product_parameters['perceived_codes']
            ideal_codes = product_parameters['ideal_codes']
            for partner, perceived_code, ideal_code in zip(
                    partners, perceived_codes, ideal_codes):

                perceived_query = cook.read_query_generator(
                    '*', f'{stakeholder}_{perceived_code}', '', '', ''
                )
                ideal_query = cook.read_query_generator(
                    '*', f'{stakeholder}_{ideal_code}', '', '', ''
                )
                perceived_data_all = pd.read_sql(
                    perceived_query, con=database_connection
                )
                ideal_data_all = pd.read_sql(
                    ideal_query, con=database_connection
                )
                relation_names = list(perceived_data_all.iloc[:, 0][0:-1])
                relations_dataframe = (
                    pd.DataFrame(
                        columns=relation_names,
                        index=relations_dataframe_index)
                )

                for country in countries:
                    ideal_data = ideal_data_all[country].values
                    perceived_data = perceived_data_all[country].values

                    perceived_percentages = (
                        [
                            perceived_data[relation_index]
                            / perceived_data[-1]
                            for relation_index, relation
                            in enumerate(relation_names)]
                    )
                    ideal_percentages = (
                        [
                            ideal_data[relation_index]
                            / ideal_data[-1]
                            for relation_index, relation
                            in enumerate(relation_names)]
                    )
                    percentage_values = (
                        [perceived_percentages, ideal_percentages]
                    )

                    for percentages, relation_type in zip(
                            percentage_values, relation_types):
                        relations_dataframe.loc[
                            country, relation_type
                        ] = percentages
                table_name = (
                    f'{stakeholder}_{table_name_root}_with_{partner}'
                    f'_for_{product}'
                )

                cook.save_dataframe(
                    relations_dataframe, table_name, groupfile_name,
                    output_folder, parameters
                )


def get_intention_weights(parameters):
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']

    products = list(parameters['products'].keys())
    pLAtYpus_parameters = parameters['pLAtYpus']

    stakeholders = pLAtYpus_parameters['stakeholders']

    intention_categories = (
            {stakeholder: parameters['intention']['categories'][stakeholder]
                for stakeholder in stakeholders}
        )
    category_weights = {}
    for product_index, product in enumerate(products):
        category_weights_unnormalised = (
            {stakeholder:
                [intention_categories[
                    stakeholder][category]['weight_of_category'][product_index]
                    for category in intention_categories[stakeholder]]
                for stakeholder in stakeholders}
        )

        category_weights[product] = (
            {stakeholder:
                [weight / sum(category_weights_unnormalised[stakeholder])
                    for weight in category_weights_unnormalised[stakeholder]]
                for stakeholder in stakeholders}
        )
    for product in products:
        print(category_weights[product])
        intention_weights = pd.DataFrame()
        for stakeholder in stakeholders:
            intention_weights[stakeholder] = (
                category_weights[product][stakeholder]
            )
        intention_weights['Category'] = (
            list(intention_categories[stakeholder].keys())
        )
        intention_weights = intention_weights.set_index('Category')
        cook.save_dataframe(
            intention_weights, f'Intention Weights {product}',
            groupfile_name, output_folder, parameters)


def get_relationship_deviations(stakeholder, parameters):
    '''
    Gets the deviations between perceived and ideal relationships.
    '''

    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    survey_parameters = parameters['survey']
    relation_definition_parameters = survey_parameters['relation_definitions']
    # relation_names = relation_definition_parameters['relation_names']
    deviations_table_name = relation_definition_parameters['deviations_table']
    deviations_table_name = f'{stakeholder}_{deviations_table_name}'
    filters_reading_relations_table = (
        relation_definition_parameters['filters_reading_relations_table']
    )
    countries = survey_parameters['countries']
    product_list = parameters['products']

    deviations_columns = relation_definition_parameters['deviations_columns']

    stakeholder_relations_parameters = (
        survey_parameters['relations'][stakeholder]
    )
    partners = stakeholder_relations_parameters['partners']

    relations_deviations_dataframe_index_tuples = (
        [
            (country, product, partner)
            for country in countries
            for product in product_list
            for partner in partners

        ]
    )

    relations_deviations_dataframe_index = (
        pd.MultiIndex.from_tuples(
            relations_deviations_dataframe_index_tuples,
            names=['Country', 'Product', 'Partner']
        )
    )

    relations_deviations_dataframe = (
        pd.DataFrame(
            columns=deviations_columns,
            index=relations_deviations_dataframe_index)
    )

    relations_table_name_root = relation_definition_parameters['table_name']

    with sqlite3.connect(source_database) as database_connection:
        for country in countries:
            for product in product_list:
                for partner in partners:
                    relations_table_name = (
                        f'{stakeholder}_{relations_table_name_root}'
                        f'_with_{partner}_for_{product}'
                    )
                    relations_table_query = (
                        cook.read_query_generator(
                            '*', relations_table_name,
                            filters_reading_relations_table,
                            ['='],
                            [f'"{country}"']

                            )
                    )
                    relations_values = (
                        pd.read_sql(
                            relations_table_query, con=database_connection
                        )
                    )
                    relation_names = list(relations_values.columns[2:])

                    deviations_squared = [
                        (relations_values[relation_name][0]
                            - relations_values[relation_name][1]) ** 2
                        for relation_name in relation_names
                    ]
                    variance = (
                        sum(deviations_squared) / len(deviations_squared)
                    )
                    standard_deviation = math.sqrt(variance)
                    table_values = [standard_deviation, 1-standard_deviation]
                    relations_deviations_dataframe.loc[
                        country, product, partner] = table_values
        cook.save_dataframe(
            relations_deviations_dataframe, deviations_table_name,
            groupfile_name, output_folder, parameters
        )
    return relations_deviations_dataframe


if __name__ == '__main__':

    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)
    get_survey_product_values(parameters)
