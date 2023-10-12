import datetime

import pandas as pd
import numpy as np
import sqlite3
import matplotlib.pyplot as plt
import matplotlib as mpl


import matplotlib
from ETS_CookBook import ETS_CookBook as cook


def get_long_term_averages(product, country, parameters):
    pLAtYpus_parameters = parameters['pLAtYpus']
    stakeholders = pLAtYpus_parameters['stakeholders']
    stakeholders_with_quotes = (
        [f'"{stakeholder}"' for stakeholder in stakeholders]
    )
    stakeholders_string = ', '.join(stakeholders_with_quotes)
    time_span = pLAtYpus_parameters['time_span']
    percentage_time_span_end_average = (
        pLAtYpus_parameters['percentage_time_span_end_average']
    )
    run_duration = time_span[1] - time_span[0]
    end_average_time_start = (
        (1-percentage_time_span_end_average)
        * run_duration
    )
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    database_file = f'{output_folder}/{groupfile_name}.sqlite3'
    source_table = f'{product}_{country}'
    average_data_query = cook.read_query_generator(
        stakeholders_string, source_table,
        ['Time'], ['>='], [end_average_time_start]
    )

    with sqlite3.connect(database_file) as database_connection:
        end_average_data = pd.read_sql(average_data_query, database_connection)
    long_term_average_values = (
        [
            np.average(end_average_data[stakeholder].values)
            for stakeholder in stakeholders
        ]
    )

    long_term_averages = dict(zip(stakeholders, long_term_average_values))

    return long_term_averages


def make_long_term_average_tables(parameters):
    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    pLAtYpus_parameters = parameters['pLAtYpus']
    stakeholders = pLAtYpus_parameters['stakeholders']
    long_term_averages_table_name_prefix = (
        pLAtYpus_parameters['long_term_averages_table_name_prefix']
    )
    countries = parameters['survey']['countries']
    products = list(parameters['products'].keys())
    for product in products:
        long_term_averages_dataframe = (
            pd.DataFrame(columns=stakeholders, index=countries)
        )
        long_term_averages_dataframe.index.name = 'Country'
        for country in countries:
            long_term_averages = (
                get_long_term_averages(product, country, parameters)
            )
            for stakeholder in stakeholders:
                long_term_averages_dataframe.loc[country][stakeholder] = (
                    long_term_averages[stakeholder]
                )
        cook.save_dataframe(
            long_term_averages_dataframe,
            f'{long_term_averages_table_name_prefix}_{product}',
            groupfile_name, output_folder, parameters
        )


def make_product_area_map(product, parameters):
    cook.register_color_bars(parameters)
    golden = (1 + 5 ** 0.5) / 2

    file_parameters = parameters['files']
    output_folder = file_parameters['output_folder']
    groupfile_name = file_parameters['groupfile_name']
    database_file = f'{output_folder}/{groupfile_name}.sqlite3'
    pLAtYpus_parameters = parameters['pLAtYpus']
    stakeholders = pLAtYpus_parameters['stakeholders']
    long_term_averages_table_name_prefix = (
        pLAtYpus_parameters['long_term_averages_table_name_prefix']
    )
    countries = parameters['survey']['countries']
    country_codes = parameters['survey']['country_codes']
    country_code_dictionary = dict(zip(countries, country_codes))
    maps_parameters = parameters['maps']
    country_code_header = maps_parameters['country_code_header']
    country_code_header_in_map_data = (
        maps_parameters['country_code_header_in_map_data']
    )
    heat_bar_map = maps_parameters['heat_bar_map']
    non_survey_country_color = maps_parameters['non_survey_country_color']
    map_title_font_size = maps_parameters['map_title_font_size']

    product_timer = datetime.datetime.now()
    source_table = f'{long_term_averages_table_name_prefix}_{product}'
    source_table_query = cook.read_query_generator(
        '*', source_table, '', '', ''
    )
    with sqlite3.connect(database_file) as database_connection:
        product_data = pd.read_sql(source_table_query, database_connection)
    product_data[country_code_header] = (
        product_data['Country'].map(country_code_dictionary)
    )

    area_data = cook.get_map_area_data(parameters)

    product_plot = (
        pd.merge(
            area_data, product_data,
            left_on=country_code_header_in_map_data,
            right_on=country_code_header
        )
    )

    values_to_plot = (
        product_plot[[stakeholder for stakeholder in stakeholders]]
    )
    lowest_value_to_plot = values_to_plot.min().min()
    highest_value_to_plot = values_to_plot.max().max()
    display_reference_scale = cook.reference_scale(
        [lowest_value_to_plot, highest_value_to_plot], 1
    )
    lowest_value_to_display = display_reference_scale[0]
    highest_value_to_display = display_reference_scale[1]
    color_bar_scale = mpl.colors.Normalize(
        vmin=lowest_value_to_display, vmax=highest_value_to_display
    )
    stakeholder_area_map_figure, (stakeholder_area_map_plots) = (
        plt.subplots(1, 3, figsize=(10 * golden, 10))
    )
    for stakeholder_index, stakeholder in enumerate(stakeholders):
        area_map_figure, area_map_plot = plt.subplots(1, 1)

        area_data.plot(
            ax=area_map_plot,
            facecolor=non_survey_country_color, edgecolor='face')
        area_data.plot(
            ax=stakeholder_area_map_plots[stakeholder_index],
            facecolor=non_survey_country_color, edgecolor='face')

        product_plot.plot(
            ax=area_map_plot, column=stakeholder,
            legend=True,
            norm=color_bar_scale,
            cmap=heat_bar_map, antialiased=True,
            edgecolor='face'
        )
        if stakeholder_index == len(stakeholders)-1:
            show_legend = True
        else:
            show_legend = False

        product_plot.plot(
            ax=stakeholder_area_map_plots[stakeholder_index],
            column=stakeholder,
            legend=show_legend,
            legend_kwds={
                'orientation': 'horizontal',
                'shrink': 3,
                'aspect': 66,
                'anchor': (1.1, 1.26)
                },
            norm=color_bar_scale,
            cmap=heat_bar_map, antialiased=True,
            edgecolor='face'
        )

        color_axis = area_map_figure.get_axes()[1]

        color_axis_yticks = color_axis.get_yticks()

        color_axis_ytick_labels = (
            [f'{y_tick:.0%}' for y_tick in color_axis_yticks]
        )

        color_axis.set_yticks(color_axis_yticks)
        color_axis.set_yticklabels(color_axis_ytick_labels)

        color_axis.set_ylabel(
            f'Engagement level'
        )

        if show_legend:
            stakeholders_color_axis = (
                stakeholder_area_map_figure.get_axes()[-1]
            )

            stakeholders_color_axis.set_xticks(color_axis_yticks)
            stakeholders_color_axis.set_xticklabels(
                color_axis_ytick_labels, fontsize=24
            )
            stakeholders_color_axis.set_xlabel(
                f'Engagement level ',
                fontsize=24
            )
            stakeholder_area_map_plots[stakeholder_index].text(
                0, 0, f'© EuroGeographics for the administrative boundaries',
                fontsize=6
            )
        area_map_plot.text(
            0, 0, f'© EuroGeographics for the administrative boundaries',
            fontsize=6
        )

        area_map_plot.axis('off')

        stakeholder_area_map_plots[stakeholder_index].axis('off')
        stakeholder_area_map_plots[stakeholder_index].set_xlim(-3e6, 5e6)
        stakeholder_area_map_plots[stakeholder_index].set_ylim(0.4e7, 1.2e7)
        stakeholder_area_map_plots[stakeholder_index].set_title(
            stakeholder, fontsize=32
        )
        new_line = '\n'
        plot_title = (
            f'Long-term average engagement of'
            f' {stakeholder} for {product}'
        )
        display_plot_title = (
            f'Long-term average engagement of'
            f'\n'
            f' {stakeholder} for {product}'
        )
        area_map_plot.set_title(
            display_plot_title, fontsize=map_title_font_size
        )
        area_map_figure.set_tight_layout(True)
        cook.save_figure(
            area_map_figure, plot_title, output_folder,
            parameters
        )

    position_plot_with_legend = (
        stakeholder_area_map_plots[-1].get_position().get_points()
    )
    y_0_plot_with_legend = position_plot_with_legend[0][1]
    position_plot_without_legend = (
        stakeholder_area_map_plots[0].get_position().get_points()
    )
    y_0_plot_without_legend = position_plot_without_legend[0][1]
    height_shift = y_0_plot_with_legend - y_0_plot_without_legend
    for stakeholder_index in range(len(stakeholders)):
        if stakeholder_index != (len(stakeholders) - 1):
            plot_position = (
                stakeholder_area_map_plots[stakeholder_index]
                .get_position().get_points()
            )
            plot_x0 = plot_position[0][0]
            plot_y0 = plot_position[0][1]
            new_plot_y0 = plot_y0 + height_shift
            plot_width = plot_position[1][0]-plot_position[0][0]
            plot_height = plot_position[1][1]-plot_position[0][1]
            new_plot_position = [plot_x0, new_plot_y0, plot_width, plot_height]
            stakeholder_area_map_plots[stakeholder_index].set_position(
                new_plot_position
            )

    stakeholder_area_map_figure.suptitle(
        f'Long-term average engagement for {product}',
        fontsize=32
    )

    stakeholder_area_map_figure.savefig(
        f'output/Long-term average engagement for {product}.png',
        bbox_inches='tight'
    )
    stakeholder_area_map_figure.savefig(
        f'output/Long-term average engagement for {product}.svg',
        bbox_inches='tight'
    )


def make_area_maps(parameters):

    products = list(parameters['products'].keys())
    print('Making maps')
    for product in products:
        product_timer = datetime.datetime.now()
        make_product_area_map(product, parameters)
        print(product, (datetime.datetime.now()-product_timer).total_seconds())


if __name__ == '__main__':
    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)
    start = datetime.datetime.now()
    make_long_term_average_tables(parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())
    make_area_maps(parameters)
    end = datetime.datetime.now()
    print((end-start).total_seconds())
