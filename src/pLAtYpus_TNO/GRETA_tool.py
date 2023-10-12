'''
This module contains the elements to build a tool for pLAtYpus, which was
first done with GRETA.
This tool would contain a number of sliders with which the user
can modify certain values:
-initial yes values (per country, product, and stakeholder),
- weights (that are pan-european, so only per product and stakeholder),
- survey category results (per country, product, and stakeholder)

The update_from_slider function updates the pLAtYpus.sqlite3 database
with the change value of a given slider. It has two arguments:
1) slider_name: The name of the slider/quantity, which
    has the following structure (so name/ID your sliders in the same way):
    type__product__stakeholder__country__survey_topic__adopt_leave
    where:
    a) type is either initial_yes, survey_topic, or intention_weight
    b) product is either autonomous_cars, or sustainable_transport,
    or cooperative_self_generation
    c) stakeholder is either citizens, business, or government
    d) country is either the country's name, or EU for weights (note that
    you can actually put anything you want (if it's a valid string), as
    weights are pan-europeanin this version of the model)
    e) survey_topic is one of the survey topics, so it does not need to be
    given for initial_yes (for this one, you can stop after giving the country)
     For survey_topic, it can be : agency_to_engage,
    emotions, environmental_outcomes, outcomes_to_the_individual_and_household,
    relation_score_citizens, relation_score_government, relation_score_business
    (not that only two of the latter three exist, as the relation score only
    pertains to the other stakeholders). Note that social norm
    is not present, as it comes from the engagement levels).
    For intention_weight, it can be: outcomes_to_the_individual_and_household,
    agency_to_engage, environmental_outcomes, social_norm, engagement_emotion,
    or dominant_relational_model
    f) adopt_leave is either Adopt or Leave (and only needed for survey_topic)

    Note that the elements need to be separated with a dunder/double underscore
2) slider_value: The new value of the quantity/slider
The function then calls the relevant updating function
(update_survey_topic_values, update_initial_yes, update_intention_weights)


The reset_to_survey function resets the values to the ones from the survey
(that is before the sliders are used). It uses the parameters as arguments.
You can get them with the following two lines of code:
    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)


The get_output_tables produces Dataframes that can be used to produce plots
for a given product. It takes the product name (autonomous_cars,
sustainable_transport, cooperative_self_generation) and the parameters as
arguments. You can get them with the following two lines of code:
    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)
The output of the function is data_from_maps, adoption_curves
data_from_maps is a DataFrame that contains the long-term averages
for engagement levels of stakeholders in each country for the topic at hand
adoption_curves is a dictionary of country DataFrames. You can get
the DataFrame of a given country by calling it (adoption_curves[country]).
You then get a DataFrame for the time-evolution if the engagement curves
of all three stakeholders in that country for teh product at hand.


The make_outputs function makes the plots/figures for a given product
and country (you can also use EU if you want to change them all,
which you should do if you change the weights,
as they apply to all countries).
'''

import datetime
import sqlite3
import shutil

import pandas as pd
import numpy as np

from ETS_CookBook import ETS_CookBook as cook

try:
    from pLAtYpus_TNO import solver
except ModuleNotFoundError:
    import solver

try:
    from pLAtYpus_TNO import maps
except ModuleNotFoundError:
    import maps


def reset_to_survey(parameters):
    '''
    The reset_to_survey function resets the values to the ones from the survey
    (that is before the sliders are used).
    It does so by copying a copy of the database fwith only the survey data.
    It uses the parameters as arguments.
    You can get them with the following two lines of code:
        parameters_file_name = 'pLAtYpus.toml'
        parameters = cook.parameters_from_TOML(parameters_file_name)
    '''
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    groupfile_name_only_survey = file_parameters['groupfile_name_only_survey']
    database_file = f'{output_folder}/{groupfile_name}.sqlite3'
    database_file_for_resets = (
        f'{output_folder}/{groupfile_name_only_survey}.sqlite3'
    )
    shutil.copy(database_file_for_resets, database_file)
    solver.get_all_evolutions(parameters)
    maps.make_long_term_average_tables(parameters)


def update_survey_topic_values(
        product, country, stakeholder, component,
        adopt_leave, new_value, parameters):
    '''
    This updates the survey topic values in the database.
    You need to provide a product, a country,
    stakeholder, a survey component, and
     if it is for adopt or leave  (you can iterate if you want
    to update several stakeholders, products, components, and/or adopt/leave),
    and the new value.
    '''
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    model_database = f'{output_folder}/{groupfile_name}.sqlite3'
    table_to_update = f'"survey_topics"'
    cook.update_database_table(
                model_database,
                table_to_update, [adopt_leave], [new_value],
                ['Product', 'Country', 'Stakeholder', 'Component'],
                ['=', '=', '=', '='],
                [
                    f'"{product}"', f'"{country}"',
                    f'"{stakeholder}"', f'"{component}"'
                ]
                )


def update_intention_weights(
        product, stakeholder, changed_intention_category,
        new_weight, parameters):
    '''
    This updates the Intention weights in the database.
    You need to provide a product, a stakeholder (you can iterate if you want
    to update several stakeholders and/or products), an intention category,
    and its new weight. The other weights will be updated accordingly, so that
    their sum is still one.
    If there are more changes, you can iterate.
    '''
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    model_database = f'{output_folder}/{groupfile_name}.sqlite3'
    weights_table_name = f'"Intention Weights {product}"'
    old_weights_query = cook.read_query_generator(
        f'Category, {stakeholder}', weights_table_name, [], [],
        []
    )
    with sqlite3.connect(model_database) as database_connection:
        old_weights = pd.read_sql(
            old_weights_query, database_connection).set_index('Category')
    old_weight_of_changed_category = (
        old_weights.loc[changed_intention_category].values[0]
    )
    intention_categories = old_weights.index
    weights_for_weight_shift_split = [
        old_weights.loc[intention_category].values[0]
        if intention_category != changed_intention_category
        else 0
        for intention_category in intention_categories
    ]
    weights_for_weight_shift_split = np.array([
        weight/sum(weights_for_weight_shift_split)
        for weight in weights_for_weight_shift_split
    ])
    # This needs to be normalised, np.array so we can multiply it by a float

    weight_shift_of_changed_category = (
        new_weight - old_weight_of_changed_category
    )

    weight_shifts_other_categories = - (
        weight_shift_of_changed_category * weights_for_weight_shift_split
    )
    # To keep the total at one

    new_weights = [
        new_weight
        if intention_category == changed_intention_category
        else
        max(
            old_weights.loc[intention_category].values[0]
            + weight_shifts_other_categories[intention_index],
            0
        )  # To avoid negative weights
        for intention_index, intention_category
        in enumerate(intention_categories)
    ]

    new_weights = [new_weight / sum(new_weights) for new_weight in new_weights]
    # To ensure that the weights are normalised

    for intention_category, weight in zip(intention_categories, new_weights):
        cook.update_database_table(
                model_database,
                weights_table_name, [stakeholder], [weight],
                ['Category'], ['='], [f'"{intention_category}"'])
    print(
        'Update all sliders (without running the solver in an infinite loop!)'
    )


def update_initial_yes(
        product, updated_country, stakeholder,
        new_initial_yes_value, parameters):
    '''
    This updates the Inital Yes values in the database.
    You need to provide a product, a country, and its new initial yes value.
    If several products/countries, stakeholders have changed, then you can
    iterate.
    '''
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    model_database = f'{output_folder}/{groupfile_name}.sqlite3'
    table_to_update = f'"Initial Yes {product}"'
    cook.update_database_table(
        model_database,
        table_to_update, [stakeholder], [new_initial_yes_value],
        ['Country'],
        ['='], [f'"{updated_country}"'])


def update_from_slider(slider_name, slider_value, parameters):
    '''
    The update_from_slider function updates the pLAtYpus.sqlite3 database
    with the change value of a given slider. It has two arguments:
    1) slider_name: The name of the slider/quantity, which
        has the following structure (so name/ID your sliders in the same way):
        type__product__stakeholder__country__survey_topic__adopt_leave
        where:
        a) type is either initial_yes, survey_topic, or intention_weight
        b) product is either autonomous_cars, or sustainable_transport,
        or cooperative_self_generation
        c) stakeholder is either citizens, business, or government
        d) country is either the country's name, or EU for weights (note that
        you can actually put anything you want (if it's a valid string), as
        weights are pan-europeanin this version of the model)
        e) survey_topic is one of the survey topics, so it does not need to
        be given
        for initial_yes (for this one, you can stop after giving the country)
        For survey_topic, it can be : agency_to_engage,
        emotions, environmental_outcomes,
        outcomes_to_the_individual_and_household,
        relation_score_citizens, relation_score_government,
        relation_score_business
        (not that only two of the latter three exist,
        as the relation score only
        pertains to the other stakeholders). Note that social norm
        is not present, as it comes from the engagement levels).
        For intention_weight, it can be:
        outcomes_to_the_individual_and_household,
        agency_to_engage, environmental_outcomes,
        social_norm, engagement_emotion,
        or dominant_relational_model
        f) adopt_leave is either Adopt or Leave
        (and only needed for survey_topic)

        Note that the elements need to be separated with a
        dunder/double underscore
    2) slider_value: The new value of the quantity/slider
    '''
    slider_split_values = slider_name.split('__')
    # The slider definitions are split by a double underscore (since
    # some elements have one underscore)
    slider_type = slider_split_values[0]
    slider_product = slider_split_values[1]
    slider_stakeholder = slider_split_values[2]
    slider_country = slider_split_values[3]
    # For weights, we use a common value (EU-level)
    if slider_type == 'initial_yes':
        update_initial_yes(
            slider_product, slider_country,
            slider_stakeholder, slider_value, parameters
        )
    elif slider_type == 'intention_weight':
        changed_intention_category = slider_split_values[4]
        update_intention_weights(
            slider_product, slider_stakeholder, changed_intention_category,
            slider_value, parameters
        )
    elif slider_type == 'survey_topic':
        slider_topic = slider_split_values[4]
        slider_adopt_leave = slider_split_values[5]
        update_survey_topic_values(
            slider_product, slider_country, slider_stakeholder,
            slider_topic, slider_adopt_leave, slider_value, parameters
        )


def make_outputs(product, changed_country, parameters):
    '''
    The make_outputs function makes the plots/figures for a given product
    and country (you can also use EU if you want to change them all,
    which you should do if you change the weights,
    as they apply to all countries).
    '''
    countries = parameters['survey']['countries']
    if changed_country != 'EU':
        countries = [changed_country]
    start = datetime.datetime.now()
    for country in countries:
        solver.get_evolutions_and_plots(product, country, parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())

    start = datetime.datetime.now()
    maps.make_long_term_average_tables(parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())

    start = datetime.datetime.now()
    maps.make_product_area_map(product, parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())


def get_output_tables(product, parameters):
    '''
    The get_output_tables produces Dataframes that can be used to produce plots
    for a given product. It takes the product name (autonomous_cars,
    sustainable_transport, cooperative_self_generation) and the parameters as
    arguments. You can get them with the following two lines of code:
        parameters_file_name = 'pLAtYpus.toml'
        parameters = cook.parameters_from_TOML(parameters_file_name)
    The output of the function is data_from_maps, adoption_curves
    data_from_maps is a DataFrame that contains the long-term averages
    for engagement levels of stakeholders in each country for the topic at hand
    adoption_curves is a dictionary of country DataFrames. You can get
    the DataFrame of a given country by calling it (adoption_curves[country]).
    You then get a DataFrame for the time-evolution if the engagement curves
    of all three stakeholders in that country for the product at hand.
    '''
    start = datetime.datetime.now()
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    model_database = f'{output_folder}/{groupfile_name}.sqlite3'

    countries = parameters['survey']['countries']

    adoption_curves = {}
    with sqlite3.connect(model_database) as database_connection:
        long_term_averages_table = f'long_term_averages_{product}'
        long_term_averages_query = cook.read_query_generator(
            '*', long_term_averages_table, [], [], []
        )
        data_for_maps = pd.read_sql(
            long_term_averages_query, database_connection
        )
        for country in countries:
            adoption_table = f'{product}_{country}'
            adoption_query = cook.read_query_generator(
                '*', adoption_table, [], [], []
            )
            adoption_curves[country] = pd.read_sql(
                adoption_query, database_connection
            )
    end = datetime.datetime.now()
    print((end-start).total_seconds())
    return data_for_maps, adoption_curves


if __name__ == '__main__':
    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)

    do_reset_to_survey = False
    if do_reset_to_survey:
        reset_to_survey(parameters)
        exit()

    updated_product = 'autonomous_cars'
    updated_country = 'Netherlands'
    updated_stakeholder = 'government'
    updated_intention_weight_category = 'social_norm'
    updated_survey_topic = 'emotions'
    updated_adopt_leave = 'Adopt'
    slider_name = (
        f'intention_weight__'
        f'{updated_product}__{updated_stakeholder}__'
        f'EU'
        f'__{updated_intention_weight_category}'
    )
    slider_value = 0.26
    update_from_slider(slider_name, slider_value, parameters)

    slider_name = (
        f'initial_yes__'
        f'{updated_product}__{updated_stakeholder}__'
        f'{updated_country}'
    )
    slider_value = 0.42
    update_from_slider(slider_name, slider_value, parameters)

    slider_name = (
        f'survey_topic__'
        f'{updated_product}__{updated_stakeholder}__'
        f'{updated_country}'
        f'__{updated_survey_topic}__{updated_adopt_leave}'
    )
    slider_value = 0.89
    update_from_slider(slider_name, slider_value, parameters)

    data_for_maps, adoption_curves = (
        get_output_tables(updated_product, parameters)
    )
    print(data_for_maps)

    print(adoption_curves[updated_country])
