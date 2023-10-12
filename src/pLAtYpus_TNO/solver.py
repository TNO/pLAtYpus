import scipy.integrate as spi
import math
import datetime
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
from ETS_CookBook import ETS_CookBook as cook
import pandas as pd
import matplotlib.ticker as mtick

try:
    from pLAtYpus_TNO import scores
except ModuleNotFoundError:
    import scores


def phase_values(time, yes, model_coefficients):
    '''
    Reads the phase values through functions in the scores module.
    '''
    stakeholders = model_coefficients['stakeholders']
    survey_scores_actions = model_coefficients['survey_scores_actions']
    phases = model_coefficients['phases']
    phase_functions = [getattr(scores, f'{phase}_score') for phase in phases]
    attention, enable, intention = (
        {action:
            np.array(
                [phase_function(
                    stakeholder, time, yes, model_coefficients)[action]
                    for stakeholder in stakeholders]
            )
            for action in survey_scores_actions}
        for phase_function in phase_functions
    )
    return attention, enable, intention


def pLAtYpus_model(time, yes, model_coefficients):
    '''
    This defines the pLAtYpus model/equations.
    '''
    attention, enable, intention = phase_values(time, yes, model_coefficients)

    adopt = (attention['Adopt'] * enable['Adopt'] * intention['Adopt'])
    leave = (attention['Leave'] * enable['Leave'] * intention['Leave'])

    return (1-yes)*adopt - yes*leave


def get_yes_evolution(
        initial_yes, model_coefficients, parameters,
        save_dataframe=True):
    '''
    This function computes the yes values that result from given
    initial yes values, following a given moddel. It does so for
    a given time span (start and end times) and a number of time steps.
    It saves the results to files and returns a dataframe with the results.
    Note that we feed the model coefficients and initial_yes values instead
    of reading them from the parameters file, with the feeding coefficients
    read from a parameters file. The reason to do this is that we want to be
    able to change these coefficients dynamically (with a slider
    on a dashboard).
    Saving the dataframe is optional (but turned on by default) because
    we might want to turn it off when playing with sliders on a dashboard.
    '''

    # We read the values from the dictionary.
    # Note that we could have done so here from the parameters file
    # dictionary, but we also want to do it dynamically (with sliders,
    # for example), so we need to pass a dictionary of variables.
    country = model_coefficients['country']
    product = model_coefficients['product']
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']

    pLAtYpus_parameters = parameters['pLAtYpus']
    time_span = pLAtYpus_parameters['time_span']
    time_steps = pLAtYpus_parameters['time_steps']
    yes_evolution_table_name = pLAtYpus_parameters['yes_evolution_table_name']
    yes_evolution_table_name = f'{product}_{country}'
    time_header = pLAtYpus_parameters['time_header']

    yes_solutions = spi.solve_ivp(
        pLAtYpus_model, t_span=time_span, y0=initial_yes,
        args=(model_coefficients,),
        # We need to pass the arguments as a tuple, with an empty
        # second part to pass a dictionary as argument
        dense_output=True
    )

    time_range = np.linspace(time_span[0], time_span[1], time_steps)
    stakeholders = pLAtYpus_parameters['stakeholders']

    yes_evolution = pd.DataFrame(
        yes_solutions.sol(time_range).T,
        index=time_range,
        columns=stakeholders
    )

    yes_evolution.index.name = time_header
    if save_dataframe:
        cook.save_dataframe(
            yes_evolution, yes_evolution_table_name,
            groupfile_name, output_folder, parameters
        )

    return yes_evolution


def plot_evolution(product, country, yes_evolution, parameters):
    '''
    Makes plots of the yes evolution and saves them to files.
    '''

    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']

    pLAtYpus_parameters = parameters['pLAtYpus']
    stakeholders = pLAtYpus_parameters['stakeholders']
    time_header = pLAtYpus_parameters['time_header']
    yes_evolution_table_name = pLAtYpus_parameters['yes_evolution_table_name']
    yes_evolution_table_name = f'{product}_{country}'

    plot_parameters = parameters['plots']
    plotting_style = plot_parameters['plotting_style']
    plt.style.use(plotting_style)

    stakeholder_color_names = plot_parameters['stakeholder_colors']
    stakeholder_colors = cook.rgb_color_list(
        stakeholder_color_names, parameters
    )

    evolution_plot_parameters = plot_parameters['evolution']

    y_min = evolution_plot_parameters['y_min']
    y_max = evolution_plot_parameters['y_max']
    use_percent = evolution_plot_parameters['use_percent']
    stakeholder_line_widths = plot_parameters['stakeholder_line_widths']
    evolution_figure, evolution_plot = plt.subplots()
    for (
        stakeholder, stakeholder_color, stakeholder_line_width) in (
            zip(stakeholders, stakeholder_colors, stakeholder_line_widths)):
        evolution_plot.plot(
            yes_evolution[stakeholder], color=stakeholder_color,
            linewidth=stakeholder_line_width, label=stakeholder
        )
    if use_percent:
        y_axis_title = evolution_plot_parameters['y_axis_title']
        evolution_plot.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    else:
        y_axis_title = evolution_plot_parameters['y_axis_title_no_percent']
    evolution_plot.legend()
    evolution_plot.set_ylim(y_min, y_max)
    evolution_plot.set_xlabel(time_header)
    evolution_plot.set_ylabel(y_axis_title)

    evolution_plot.set_title(f'{product} {country}')
    evolution_figure.tight_layout()
    cook.save_figure(
        evolution_figure, yes_evolution_table_name,
        output_folder, parameters
    )
    plt.close()


def get_survey_scores(parameters):

    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    model_database = f'{output_folder}/{groupfile_name}.sqlite3'
    survey_topics_table_name = file_parameters['survey_topics_table_name']
    survey_topics_query = cook.read_query_generator(
        '*', survey_topics_table_name, '', '', ''
    )
    with sqlite3.connect(model_database) as database_connection:
        survey_scores_all = pd.read_sql(
            survey_topics_query, database_connection
        )
        survey_scores_all = (
            survey_scores_all.set_index(
                ['Country', 'Product', 'Stakeholder', 'Component']
                )
        )
    return survey_scores_all


def plot_survey_scores(parameters):
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    survey_scores_actions = parameters['survey']['survey_scores_actions']
    plot_parameters = parameters['plots']
    plot_style = plot_parameters['plotting_style']
    stakeholder_colors = plot_parameters['stakeholder_colors']
    plt.style.use(plot_style)
    survey_scores = get_survey_scores(parameters)
    stakeholders = parameters['pLAtYpus']['stakeholders']

    countries = sorted(
        list(set(survey_scores.index.get_level_values('Country')))
    )
    products = sorted(
        list(set(survey_scores.index.get_level_values('Product')))
    )
    for country in countries:
        for action in survey_scores_actions:
            for product_index, product in enumerate(products):
                survey_scores_figure = plt.figure()
                product_plot = (
                    survey_scores_figure.add_subplot(
                        111, polar=True
                    )
                )
                for stakeholder, stakeholder_color in zip(
                        stakeholders, stakeholder_colors):
                    stakeholder_color = cook.get_rgb_from_name(
                        stakeholder_color, parameters
                    )
                    scores_to_plot = (
                        survey_scores
                        .loc[country, product, stakeholder][action]
                    )
                    markers = [0, 0.25, 0.50, 0.75, 1.0]
                    marker_labels = ['0%', '25%', '50%', '75%', '100%']
                    data_labels = []
                    data_values = []
                    series_label = stakeholder
                    spider_color = stakeholder_color
                    spider_marker = 'o'
                    spider_linewidth = 2
                    spider_alpha = 0.26
                    for component in scores_to_plot.index:
                        if component != 'one':
                            if component[0:8] != 'relation':
                                data_labels.append(component)
                                data_values.append(
                                    float(scores_to_plot.loc[component])
                                )
                    relational_model_components = (
                        parameters['intention']['categories'][stakeholder][
                            'dominant_relational_model']['survey_components']
                    )
                    relational_model_weights = (
                        parameters['intention']['categories'][stakeholder][
                            'dominant_relational_model'][
                                'survey_component_weights']
                    )
                    relational_model_score = 0

                    for weight, component in zip(
                            relational_model_weights,
                            relational_model_components):
                        relational_model_score += (
                            weight * float(scores_to_plot.loc[component])
                        )

                    data_labels.append('relational_model')
                    data_values.append(relational_model_score)

                    product_plot = cook.make_spider_chart(
                        product_plot,
                        series_label,
                        data_labels, data_values, markers, marker_labels,
                        spider_color, spider_marker, spider_linewidth,
                        spider_alpha
                    )
                    product_plot.legend(fontsize=6)
                    product_plot.set_title(f'{product}', fontsize=12)
                    product_plot.set_yticks(product_plot.get_yticks())
                    product_plot.set_yticklabels(
                        product_plot.get_yticklabels(), fontsize=8
                    )
                    angles = (
                        np.linspace(0, 2*np.pi, len(data_labels),
                                    endpoint=False)
                    )
                    angles = np.concatenate((angles, [angles[0]]))
                    product_plot.set_thetagrids(angles * 180/np.pi, fontsize=8)
                    survey_scores_figure.suptitle(
                        f'Survey scores for {action} in {country}',
                        fontsize=14

                    )

                    product_plot.spines['polar'].set_color('silver')
                    product_plot.spines['polar'].set_alpha(0.26)
                    plot_spines = product_plot.spines

                    # for plot_spine in plot_spines:
                    #     print(plot_spine)

                    survey_scores_figure.set_tight_layout(True)
                    cook.save_figure(
                        survey_scores_figure,
                        f'{product} survey scores for {action} in {country}',
                        output_folder,
                        parameters
                    )
                    plt.close()


def intention_weights_plots(parameters):
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    file_root = 'Intention Weights'

    products = [
        'autonomous_cars', 'sustainable_transport',
        'cooperative_self_generation'
    ]
    golden = (1 + 5 ** 0.5) / 2
    intention_figure, intention_plots = (
        plt.subplots(1, 3, figsize=(60 * golden, 60))
    )
    color_names = [
        'GRETA_darkest',
        'GRETA_dark',
        'kraken_boundless_blue',
        'kraken_shadow_blue',
        'kraken_ice_blue',
        'GRETA_lightest'

    ]
    plt.style.use('fivethirtyeight')
    category_colors = [
        cook.get_rgb_from_name(color_name, parameters)
        for color_name in color_names
    ]
    for product_index, product in enumerate(products):

        source_data = pd.read_csv(
            f'{output_folder}/{file_root} {product}.csv'
        ).set_index('Category').T
        categories = list(source_data.columns)
        source_data.plot.barh(
            ax=intention_plots[product_index], stacked=True,
            color=category_colors)
        # plot_legend = intention_plots[product_index].get_legend()
        intention_plots[product_index].get_legend().remove()
        intention_plots[product_index].set_xticks([0, 0.25, 0.50, 0.75, 1])
        intention_plots[product_index].set_xticklabels(
            ['0%', '25%', '50%', '75%', '100%'],
            fontsize=96
        )
        intention_plots[product_index].set_yticks(
            intention_plots[product_index].get_yticks())
        intention_plots[product_index].set_yticklabels(
            intention_plots[product_index].get_yticklabels(),
            fontsize=84
            )
        if product_index > 0:
            intention_plots[product_index].set_yticks([])
        intention_plots[product_index].set_title(
            product,
            fontsize=108
            )
        for value_to_show in intention_plots[product_index].containers:
            intention_plots[product_index].bar_label(
                value_to_show, label_type='center', fmt='{:,.0%}',
                fontsize=77
            )
    intention_figure.suptitle(
        'Intention Weights\n',
        fontsize=160
        )
    intention_figure.legend(
        loc='lower center',
        ncol=3,
        # prop = {'size':7},
        bbox_to_anchor=[0.5, -0.015],
        labels=categories,
        fontsize=96
        )
    plt.margins(x=0)

    plt.savefig(f'{output_folder}/Intention Weights.png', bbox_inches='tight')
    plt.savefig(f'{output_folder}/Intention Weights.svg', bbox_inches='tight')


def get_evolutions_and_plots(product, country, parameters):
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    pLAtYpus_parameters = parameters['pLAtYpus']
    phases = pLAtYpus_parameters['phases']

    stakeholders = pLAtYpus_parameters['stakeholders']

    intention_categories = (
            {stakeholder: parameters['intention']['categories'][stakeholder]
                for stakeholder in stakeholders}
        )

    model_database = f'{output_folder}/{groupfile_name}.sqlite3'

    with sqlite3.connect(model_database) as database_connection:

        weight_query = (
            cook.read_query_generator(
                '*', f'"Intention Weights {product}"', [], [], []
            )
        )
        category_weights = pd.read_sql(weight_query, database_connection)

    survey_scores_all = get_survey_scores(parameters)
    attention_inputs = parameters['attention']

    survey_scores = survey_scores_all.loc[(country, product)]

    survey_scores_actions = (
        parameters['survey']['survey_scores_actions']
    )
    categories_intention_scores, categories_yes_codes = (
        scores.get_categories_intention_scores(
            stakeholders,
            survey_scores, survey_scores_actions, intention_categories
        )
    )

    product_parameters = parameters['products'][product]
    model_coefficients = {}
    model_coefficients['phases'] = phases
    model_coefficients['country'] = country
    model_coefficients['product'] = product
    model_coefficients['survey_scores'] = survey_scores
    model_coefficients['category_weights'] = category_weights
    model_coefficients['categories_intention_scores'] = (
        categories_intention_scores
    )
    model_coefficients['categories_yes_codes'] = categories_yes_codes
    survey_enable_parameters = (
        product_parameters['survey_enable_parameters']
    )
    model_coefficients['survey_enable_parameters'] = (
        survey_enable_parameters
    )
    availability_threshold_adopt = (
        product_parameters['availability_threshold_adopt']
    )
    model_coefficients['availability_threshold_adopt'] = (
        availability_threshold_adopt
    )
    availability_threshold_leave = (
        product_parameters['availability_threshold_leave']
    )
    model_coefficients['availability_threshold_leave'] = (
        availability_threshold_leave
    )
    model_coefficients['intention_categories'] = intention_categories
    model_coefficients['survey_scores_actions'] = survey_scores_actions
    model_coefficients['stakeholders'] = stakeholders
    model_coefficients['attention_inputs'] = attention_inputs
    initial_yes_table_name = f'"Initial Yes {product}"'
    initial_yes_query = (
        cook.read_query_generator(
            '*', initial_yes_table_name, ['Country'],
            ['='], [f'"{country}"']
        )
    )
    source_database = f'{output_folder}/{groupfile_name}.sqlite3'
    with sqlite3.connect(source_database) as database_connection:
        initial_yes = (
            pd.read_sql(initial_yes_query, database_connection)
        )[stakeholders].values[0]

    yes_evolution = get_yes_evolution(
        initial_yes, model_coefficients, parameters)
    plot_evolution(
        product, country, yes_evolution, parameters
    )


def get_all_evolutions(parameters):

    countries = parameters['survey']['countries']
    products = list(parameters['products'].keys())

    for product in products:
        print(product)
        for country in countries:
            print(country)
            get_evolutions_and_plots(product, country, parameters)


def get_all_evolutions_and_plots(parameters):

    get_all_evolutions(parameters)
    do_plot_survey_scores = parameters['plots']['do_plot_survey_scores']
    do_plot_intention_weights = (
        parameters['plots']['do_plot_intention_weights']
    )
    if do_plot_survey_scores:
        plot_survey_scores(parameters)
    if do_plot_intention_weights:
        intention_weights_plots(parameters)


if __name__ == '__main__':
    start = datetime.datetime.now()
    parameters_file_name = 'pLAtYpus.toml'

    parameters = cook.parameters_from_TOML(parameters_file_name)
    get_all_evolutions_and_plots(parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())
