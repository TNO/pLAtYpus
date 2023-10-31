
import pandas as pd
import numpy as np
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

        relations_overlap_dataframe = (
            get_relationship_overlap(stakeholder, parameters)
        )

        use_overlap = (
            parameters['survey']['relation_definitions']['use_overlap']
        )
        overlap_column_header = (
            parameters['survey']['relation_definitions']['overlap_columns'][0]
        )
        partners = parameters['survey']['relations'][stakeholder]['partners']
        for country in countries:
            for partner in partners:
                for product in products:
                    component = f'relation_score_{partner}'
                    if use_overlap:
                        adopt_value = (
                            relations_overlap_dataframe.loc[
                                (country, product, partner)
                            ][overlap_column_header]
                        )
                    else:
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
    # Now that we iterated over the stakeholders, we can get the
    # bidirectional and product relationship scores
    get_bidirectional_relationship_deviations(parameters)
    get_product_relation_deviations(parameters)
    get_bidirectional_relationship_overlap(parameters)
    get_product_relation_overlap(parameters)
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


def get_relationship_overlap(stakeholder, parameters):
    '''
    Gets the overlap between perceived and ideal relationships.
    For each, we look at the ratio between perceived and ideal..
    If ideal is higher than perceived, we invert the ratio
    (to get the overlap, the smaller of the two needs to be the numerator)
    '''

    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    survey_parameters = parameters['survey']
    relation_definition_parameters = survey_parameters['relation_definitions']
    overlap_table_name = relation_definition_parameters['overlap_table']
    overlap_table_name = f'{stakeholder}_{overlap_table_name}'
    filters_reading_relations_table = (
        relation_definition_parameters['filters_reading_relations_table']
    )
    countries = survey_parameters['countries']
    product_list = parameters['products']

    overlap_columns = relation_definition_parameters['overlap_columns']

    stakeholder_relations_parameters = (
        survey_parameters['relations'][stakeholder]
    )
    partners = stakeholder_relations_parameters['partners']

    relations_overlap_dataframe_index_tuples = (
        [
            (country, product, partner)
            for country in countries
            for product in product_list
            for partner in partners

        ]
    )

    relations_overlap_dataframe_index = (
        pd.MultiIndex.from_tuples(
            relations_overlap_dataframe_index_tuples,
            names=['Country', 'Product', 'Partner']
        )
    )

    relations_overlap_dataframe = (
        pd.DataFrame(
            columns=overlap_columns,
            index=relations_overlap_dataframe_index)
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

                    perceived_relations = [
                        relations_values[relation_name][0]
                        for relation_name in relation_names
                    ]
                    ideal_relations = [
                        relations_values[relation_name][1]
                        for relation_name in relation_names
                    ]

                    overlaps = [
                        perceived_relation / ideal_relation
                        if ideal_relation != 0
                        else 0  # To avoid divisions by zero
                        for perceived_relation, ideal_relation
                        in zip(perceived_relations, ideal_relations)
                    ]
                    # If ideal is larger than perceived, we invert the
                    # fraction to get the actual overlap
                    overlaps = [
                        overlap
                        if overlap <= 1
                        else
                        1 / overlap
                        for overlap in overlaps
                    ]

                    average_overlap = np.average(overlaps)
                    relations_overlap_dataframe.loc[
                        country, product, partner] = average_overlap
        cook.save_dataframe(
            relations_overlap_dataframe, overlap_table_name,
            groupfile_name, output_folder, parameters
        )

    return relations_overlap_dataframe


def get_bidirectional_relationship_overlap(parameters):
    '''
    This computes the bidirectional relation overlap, i.e. how
    good (or bad) the relation between two parties is.
    '''
    stakeholders = parameters['pLAtYpus']['stakeholders']
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    survey_parameters = parameters['survey']
    relation_definition_parameters = survey_parameters['relation_definitions']
    overlap_table_name_root = (
        relation_definition_parameters['overlap_table']
    )
    bidirectional_overlap_table = (
        relation_definition_parameters['bidirectional_overlap_table']
    )
    overlap_tables = {}
    countries = survey_parameters['countries']
    product_list = parameters['products']
    with sqlite3.connect(source_database) as database_connection:
        for stakeholder in stakeholders:
            overlap_table_name = (
                f'{stakeholder}_{overlap_table_name_root}'
            )
            relations_table_query = (
                cook.read_query_generator(
                    '*', overlap_table_name, [], [], []
                )
            )
            overlap_tables[stakeholder] = pd.read_sql(
                relations_table_query, database_connection
            ).set_index(['Country', 'Product', 'Partner'])
    stakeholder_pairs = []
    for stakeholder_index, stakeholder in enumerate(stakeholders):
        for partner in stakeholders[stakeholder_index+1:]:
            stakeholder_pairs.append((stakeholder, partner))

    bidirectional_relationships_index_tuples = [
        (country, product, pair)
        for country in countries
        for product in product_list
        for pair in stakeholder_pairs
    ]
    bidirectional_relationships_index = pd.MultiIndex.from_tuples(
        bidirectional_relationships_index_tuples,
        names=['Country', 'Product', 'Pair']
    )
    bidirectional_relationship_overlap = pd.DataFrame(
        columns=(
            parameters['survey']['relation_definitions']['overlap_columns']
        ),
        index=bidirectional_relationships_index
    )
    for country in countries:
        for product in product_list:
            for stakeholder_pair in stakeholder_pairs:

                average_overlap = (
                    overlap_tables[stakeholder_pair[0]]
                    .loc[country, product, stakeholder_pair[1]]
                    +
                    overlap_tables[stakeholder_pair[1]]
                    .loc[country, product, stakeholder_pair[0]]
                ) / 2

                bidirectional_relationship_overlap.loc[
                    country, product, stakeholder_pair] = average_overlap

    # sqlite3 does not support tuples, so we convert the pair names
    # to strings
    bidirectional_relationship_overlap = (
        bidirectional_relationship_overlap.reset_index()
    )
    bidirectional_relationship_overlap['Pair'] = (
        bidirectional_relationship_overlap['Pair'].astype('str')
    )
    cook.save_dataframe(
            bidirectional_relationship_overlap,
            bidirectional_overlap_table,
            groupfile_name, output_folder, parameters
        )


def get_product_relation_overlap(parameters):
    '''
    This gets the relation overlap for a given product.
    We take the average overlap for that given product to get a general
    overlap score.
    '''
    stakeholders = parameters['pLAtYpus']['stakeholders']
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    survey_parameters = parameters['survey']
    relation_definition_parameters = survey_parameters['relation_definitions']
    product_overlap_table = (
        relation_definition_parameters['product_overlap_table']
    )
    overlap_table_name_root = (
        relation_definition_parameters['overlap_table']
    )
    overlap_tables = {}
    countries = survey_parameters['countries']
    product_list = parameters['products']
    with sqlite3.connect(source_database) as database_connection:
        for stakeholder in stakeholders:
            overlap_table_name = (
                f'{stakeholder}_{overlap_table_name_root}'
            )
            relations_table_query = (
                cook.read_query_generator(
                    '*', overlap_table_name, [], [], []
                )
            )
            overlap_tables[stakeholder] = pd.read_sql(
                relations_table_query, database_connection
            ).set_index(['Country', 'Product', 'Partner'])
    product_relationships_index_tuples = [
        (country, product)
        for country in countries
        for product in product_list
    ]
    product_relationships_index = pd.MultiIndex.from_tuples(
        product_relationships_index_tuples,
        names=['Country', 'Product']
    )
    overlap_columns = (
        parameters['survey']['relation_definitions']['overlap_columns']
    )
    product_relationship_overlap = pd.DataFrame(
        columns=overlap_columns,
        index=product_relationships_index
    )
    for country in countries:
        for product in product_list:
            average_overlap = (
                sum(
                    sum(
                        overlap_tables[stakeholder]
                        .loc[country, product][overlap_columns[0]]
                    )
                    for stakeholder in stakeholders
                )
                /
                (len(stakeholders)*(len(stakeholders)-1))
                # If you have a division by zero,
                # that's because you only have one stakeholder,
                # which would make this meaningless.
            )

            product_relationship_overlap.loc[country, product] = (
                average_overlap
            )
    cook.save_dataframe(
            product_relationship_overlap,
            product_overlap_table,
            groupfile_name, output_folder, parameters
        )


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


def get_bidirectional_relationship_deviations(parameters):
    '''
    This computes the bidirectional relation deviations, i.e. how
    good (or bad) the relation between two parties is.
    '''
    stakeholders = parameters['pLAtYpus']['stakeholders']
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    survey_parameters = parameters['survey']
    relation_definition_parameters = survey_parameters['relation_definitions']
    deviations_table_name_root = (
        relation_definition_parameters['deviations_table']
    )
    bidirectional_deviations_table = (
        relation_definition_parameters['bidirectional_deviations_table']
    )
    deviations_tables = {}
    countries = survey_parameters['countries']
    product_list = parameters['products']
    with sqlite3.connect(source_database) as database_connection:
        for stakeholder in stakeholders:
            deviations_table_name = (
                f'{stakeholder}_{deviations_table_name_root}'
            )
            relations_table_query = (
                cook.read_query_generator(
                    '*', deviations_table_name, [], [], []
                )
            )
            deviations_tables[stakeholder] = pd.read_sql(
                relations_table_query, database_connection
            ).set_index(['Country', 'Product', 'Partner'])
    stakeholder_pairs = []
    for stakeholder_index, stakeholder in enumerate(stakeholders):
        for partner in stakeholders[stakeholder_index+1:]:
            stakeholder_pairs.append((stakeholder, partner))

    bidirectional_relationships_index_tuples = [
        (country, product, pair)
        for country in countries
        for product in product_list
        for pair in stakeholder_pairs
    ]
    bidirectional_relationships_index = pd.MultiIndex.from_tuples(
        bidirectional_relationships_index_tuples,
        names=['Country', 'Product', 'Pair']
    )
    bidirectional_relationship_deviations = pd.DataFrame(
        columns=(
            parameters['survey']['relation_definitions']['deviations_columns']
        ),
        index=bidirectional_relationships_index
    )
    for country in countries:
        for product in product_list:
            for stakeholder_pair in stakeholder_pairs:
                # The variance is the sum of the squares of the two deviations
                # corresponding to the pair, divided by two
                variance = (
                    (
                        deviations_tables[stakeholder_pair[0]]
                        .loc[country, product, stakeholder_pair[1]]
                        ['Standard deviation']
                    ) ** 2
                    +
                    (
                        deviations_tables[stakeholder_pair[1]]
                        .loc[country, product, stakeholder_pair[0]]
                        ['Standard deviation']
                    ) ** 2
                ) / 2
                standard_deviation = math.sqrt(variance)
                relation_score = 1 - standard_deviation
                bidirectional_relationship_deviations.loc[
                    country, product, stakeholder_pair] = [
                        standard_deviation, relation_score
                    ]
    # sqlite3 does not support tuples, so we convert the pair names
    # to strings
    bidirectional_relationship_deviations = (
        bidirectional_relationship_deviations.reset_index()
    )
    bidirectional_relationship_deviations['Pair'] = (
        bidirectional_relationship_deviations['Pair'].astype('str')
    )
    cook.save_dataframe(
            bidirectional_relationship_deviations,
            bidirectional_deviations_table,
            groupfile_name, output_folder, parameters
        )


def get_product_relation_deviations(parameters):
    '''
    This gets the relation deviations for a given product.
    We sum the squares of all deviations for a given product,
    divide by the number of relationships, and take the square root, to
    get a general standard deviation for this product (and a relation score,
    which is 1-standard deviation)
    '''
    stakeholders = parameters['pLAtYpus']['stakeholders']
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    survey_parameters = parameters['survey']
    relation_definition_parameters = survey_parameters['relation_definitions']
    product_deviations_table = (
        relation_definition_parameters['product_deviations_table']
    )
    deviations_table_name_root = (
        relation_definition_parameters['deviations_table']
    )
    deviations_tables = {}
    countries = survey_parameters['countries']
    product_list = parameters['products']
    with sqlite3.connect(source_database) as database_connection:
        for stakeholder in stakeholders:
            deviations_table_name = (
                f'{stakeholder}_{deviations_table_name_root}'
            )
            relations_table_query = (
                cook.read_query_generator(
                    '*', deviations_table_name, [], [], []
                )
            )
            deviations_tables[stakeholder] = pd.read_sql(
                relations_table_query, database_connection
            ).set_index(['Country', 'Product', 'Partner'])
    product_relationships_index_tuples = [
        (country, product)
        for country in countries
        for product in product_list
    ]
    product_relationships_index = pd.MultiIndex.from_tuples(
        product_relationships_index_tuples,
        names=['Country', 'Product']
    )
    product_relationship_deviations = pd.DataFrame(
        columns=(
            parameters['survey']['relation_definitions']['deviations_columns']
        ),
        index=product_relationships_index
    )
    for country in countries:
        for product in product_list:
            total_deviations_squared = 0
            for stakeholder in stakeholders:
                total_deviations_squared += (
                    sum(
                        deviations_tables[stakeholder]
                        .loc[country, product]['Standard deviation'].values**2
                    )
                )
            variance = (
                total_deviations_squared
                /
                (len(stakeholders)*(len(stakeholders)-1))
                # If you have a division by zero,
                # that's because you only have one stakeholder,
                # which would make this meaningless.
            )

            standard_deviation = math.sqrt(variance)
            relation_score = 1 - standard_deviation
            product_relationship_deviations.loc[country, product] = (
                [standard_deviation, relation_score]
            )
    cook.save_dataframe(
            product_relationship_deviations,
            product_deviations_table,
            groupfile_name, output_folder, parameters
        )


if __name__ == '__main__':

    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)
    # stakeholders = parameters['pLAtYpus']['stakeholders']
    # for stakeholder in stakeholders:
    #     print(stakeholder)
    #     relations_overlap_dataframe = (
    #         get_relationship_overlap(stakeholder, parameters)
    #     )
    #     print(relations_overlap_dataframe)
    get_survey_product_values(parameters)
