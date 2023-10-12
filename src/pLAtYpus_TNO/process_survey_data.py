

import os
import tomllib
import sqlite3

import openpyxl
import pandas as pd
import numpy as np

from ETS_CookBook import ETS_CookBook as cook


def read_source_sheet(stakeholder, parameters):
    '''
    This function reads the raw data and cleans it up.
    It returns a dictionary with the cleaned up values.
    This dictionary has the topics/question codes as keys.
    It does so for a given stakeholder
    '''

    stakeholders = parameters['pLAtYpus']['stakeholders']
    survey_data_source_parameters = parameters['survey']['data']['source']
    source_sheets = survey_data_source_parameters['source_sheets']
    source_stakeholder_labels = (
        survey_data_source_parameters['source_stakeholder_labels']
    )
    stakeholder_label_dictionary = (
        dict(zip(stakeholders, source_stakeholder_labels))
    )
    stakeholder_label = stakeholder_label_dictionary[stakeholder]

    country_names = parameters['survey']['countries']
    # Tomli reads the keys as strings, but we need integers (as the columns
    # are integers)
    # We need to shift this by 4 because teh data starts in the 4th column
    country_names = {
        int(country_number+4): country
        for country_number, country in enumerate(country_names)
    }

    source_prefix = survey_data_source_parameters['source_prefix']
    source_suffix = survey_data_source_parameters['source_suffix']
    source_extension = survey_data_source_parameters['source_extension']
    source_folder = survey_data_source_parameters['source_folder']
    source_file = (
        f'{source_folder}/{source_prefix}{stakeholder_label}'
        f'{source_suffix}{source_extension}'
    )
    source_sheet_dictionary = dict(zip(stakeholders, source_sheets))
    source_sheet = source_sheet_dictionary[stakeholder]

    # This gives the number of merged rows for topic headers
    topic_merged_rows_list = survey_data_source_parameters['topic_merged_rows']
    topic_merged_rows_dicttionary = (
        dict(zip(stakeholders, topic_merged_rows_list))
    )
    topic_merged_rows = topic_merged_rows_dicttionary[stakeholder]

    # This is the raw data we want to process (we dont use its headers)
    raw_data = pd.read_excel(
        source_file, sheet_name=source_sheet, header=None
    )
    # The topics and questions are in the first column
    question_headers = raw_data[0]
    # We want a list of topics, questions, and their rows
    topics = []
    topic_rows = []
    questions = []
    question_rows = []
    # We also need to know the question sizes (i.e. the size of the
    # corresponding arrays)
    array_sizes = []

    # We iterate through the question headers
    for row_index, question_header in enumerate(question_headers):
        # Questions and topics are not empty/nan
        if question_header == question_header:
            # To avoid issues with going further than the last entry
            if row_index < (len(question_headers)-2):
                # We check if the next two  values are empty/nan for citizens
                # For others, it is the next value only (less celle merged)
                # Was two for citizens, but does not seem to work for
                # business and government
                if stakeholder == 'citizens':
                    if (
                            (
                                question_headers[row_index+1] !=
                                question_headers[row_index+1]
                            )
                            and
                            (
                                question_headers[row_index+2] !=
                                question_headers[row_index+2]
                            )
                            ):
                        # If the topic_merged_rows-th next is not empty,
                        # then it's a topic
                        if (
                                question_headers[row_index+topic_merged_rows]
                                ==
                                question_headers[row_index+topic_merged_rows]):
                            topics.append(question_header)
                            topic_rows.append(row_index)
                        # Otherwise, it's a question
                        else:
                            questions.append(question_header)
                            question_rows.append(row_index)
                else:
                    if (
                            (
                                question_headers[row_index+1] !=
                                question_headers[row_index+1]
                            )
                            ):
                        # If the topic_merged_rows-th next is not empty,
                        # then it's a topic
                        if (
                                question_headers[row_index+topic_merged_rows]
                                ==
                                question_headers[row_index+topic_merged_rows]):
                            topics.append(question_header)
                            topic_rows.append(row_index)
                        # Otherwise, it's a question
                        else:
                            questions.append(question_header)
                            question_rows.append(row_index)

    topic_dataframe = pd.DataFrame.from_dict(
        dict(zip(topics, questions)), orient='index'
    )

    topic_dataframe.index.name = 'Topic'
    topic_dataframe.rename(columns={0: 'Question'}, inplace=True)
    for topic_index, topic in enumerate(topic_dataframe.index.values):
        topic_dataframe.at[topic, 'Sheet name'] = f'Sheet_{topic_index}'

    # We can look at the size of each array
    for row_index in question_rows:
        array_size = 0
        count_index = 1
        # We count the empty values, which give us the array size
        while (
                question_headers[row_index+count_index] !=
                question_headers[row_index+count_index]):
            array_size += 1
            count_index += 1
        array_sizes.append(array_size)

    # We now can extract the arrays that will be stored in a dictionary
    topic_answers = {}
    for row_index, array_size, question, topic in zip(
            question_rows, array_sizes, questions, topics):
        raw_array = raw_data.iloc[row_index:row_index+array_size+1]
        count_array = raw_array.dropna(subset=1)
        count_array = count_array.set_index(1)
        count_array.index.name = question
        count_array = count_array.iloc[:, 3:19]
        count_array.rename(columns=country_names, inplace=True)
        # We will need to remove annotations, so we need to convert the
        # array to strings (and then back to integers)
        count_array = count_array.astype(str)

        for column in count_array.columns:

            # count_array[column] = (
            #     count_array[column].str.extract(pat='(\d+)', expand=False)
            # )
            # We remove letters (used to annotate) from the answers
            count_array[column] = (
                count_array[column].str.replace('\D', '', regex=True)
            )
            # We have some zeroes that are annotated with numbers
            # So we find them and replace the value with zero

            zeroes_with_annotations = count_array[column].str.startswith('0')
            count_array.loc[zeroes_with_annotations, column] = 0

        # We convert the values to integers
        count_array = count_array.astype(int)

        topic_answers[topic] = count_array

    return topic_answers, topic_dataframe


def write_full_processed_data(
        parameters, topic_answers, topic_dataframe, stakeholder):
    '''
    This function writes all the topics to an Excel file
    '''
    survey_data_parameters = parameters['survey']['data']

    output_parameters = survey_data_parameters['output']
    output_folder = output_parameters['output_folder']
    full_output_file_prefix = output_parameters['full_output_file_prefix']
    full_output_file_extension = (
        output_parameters['full_output_file_extension']
    )
    full_output_file = (
        f'{output_folder}/{full_output_file_prefix}_{stakeholder}'
        f'{full_output_file_extension}'
    )
    writing_engine = output_parameters['writing_engine']

    if not os.path.isfile(full_output_file):
        topic_dataframe.to_excel(
            full_output_file, sheet_name=f'{stakeholder}_Topics'
        )

    my_writer = pd.ExcelWriter(
        full_output_file, engine=writing_engine, mode='a',
        if_sheet_exists='replace'
    )

    with my_writer:

        topic_dataframe.to_excel(my_writer, f'{stakeholder}_Topics')
        for topic_sheet, topic in zip(
                topic_dataframe['Sheet name'], topic_answers):
            topic_answers[topic].to_excel(
                    my_writer, sheet_name=topic_sheet
                )

    database_file_name = output_parameters['database_file_name']
    database_file = f'{output_folder}/{database_file_name}'
    with sqlite3.connect(database_file) as database_connection:
        topic_dataframe.to_sql(
            f'{stakeholder}_Topics',
            con=database_connection, if_exists='replace'
        )

        for topic in topic_answers:
            topic_clean = topic.replace(' ', '_')
            topic_clean = topic_clean.replace('’', '_')
            topic_clean = topic_clean.replace('?', '_')
            topic_clean = topic_clean.replace("'", '_')

            topic_answers[topic].to_sql(
                f'{stakeholder}_{topic_clean}',
                con=database_connection, if_exists='replace'
            )


if __name__ == '__main__':

    parameters_file_name = 'pLAtYpus.toml'
    parameters = cook.parameters_from_TOML(parameters_file_name)
    stakeholders = parameters['pLAtYpus']['stakeholders']
    for stakeholder in stakeholders:
        topic_answers, topic_dataframe = read_source_sheet(
            stakeholder, parameters
        )
        print(stakeholder)

        write_full_processed_data(
            parameters, topic_answers, topic_dataframe,
            stakeholder
        )
