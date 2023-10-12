import pandas as pd
import sqlite3
from ETS_CookBook import ETS_CookBook as cook
import numpy as np
import datetime


def attention_score(stakeholder, time, yes, model_coefficients):
    attention_inputs = model_coefficients['attention_inputs']
    stakeholders = model_coefficients['stakeholders']
    survey_scores_actions = model_coefficients['survey_scores_actions']
    attention_score = {
        action:
        attention_inputs[action][stakeholders.index(stakeholder)]
        for action in survey_scores_actions}
    return attention_score


def enable_score(stakeholder, time, yes, model_coefficients):

    if stakeholder == 'citizens':
        survey_scores = model_coefficients['survey_scores']
        no = [1-this_yes for this_yes in yes]
        survey_enable_parameters = (
                model_coefficients['survey_enable_parameters']
            )

        enable_score_adopt = np.prod([
            survey_scores.loc[
                    f'{survey_enable_parameter}']['Adopt']
            for survey_enable_parameter in survey_enable_parameters
        ]
        )

        availability_threshold_adopt = (
            model_coefficients['availability_threshold_adopt']
        )
        if yes[1] < availability_threshold_adopt:
            enable_score_adopt *= yes[1]

        enable_score_leave = 1

        availability_threshold_leave = (
            model_coefficients['availability_threshold_leave']
        )

        if no[1] < availability_threshold_leave:
            enable_score_leave *= no[1]

    else:
        enable_score_adopt = 1
        enable_score_leave = 1
    return {'Adopt': enable_score_adopt, 'Leave': enable_score_leave}


def category_intention_score(
        stakeholder,
        category, survey_scores, survey_scores_actions, intention_categories):

    category_parameters = intention_categories[stakeholder][category]
    survey_components = category_parameters['survey_components']
    survey_component_weights = category_parameters['survey_component_weights']
    component_scores = (
        {action:
            np.array([
                float(survey_scores.loc[stakeholder, component][action])
                for component in survey_components
            ])
            for action in survey_scores_actions}
    )
    category_intention_score = (
        {action:
            (np.array(component_scores[action]) * survey_component_weights)
            for action in survey_scores_actions}
    )
    yes_functions_adopt = category_parameters['yes_functions_adopt']
    yes_functions_leave = category_parameters['yes_functions_leave']
    yes_stakeholders = category_parameters['yes_stakeholders']
    yes_codes_adopt = (
        [
            f'{yes_function}_{yes_stakeholder}'
            for yes_function, yes_stakeholder
            in zip(yes_functions_adopt, yes_stakeholders)
        ]
    )
    yes_codes_leave = (
        [
            f'{yes_function}_{yes_stakeholder}'
            for yes_function, yes_stakeholder
            in zip(yes_functions_leave, yes_stakeholders)
        ]
    )
    category_yes_codes = {
        'Adopt': yes_codes_adopt,
        'Leave': yes_codes_leave
    }

    return category_intention_score, category_yes_codes


def get_categories_intention_scores(
        stakeholders,
        survey_scores, survey_scores_actions, intention_categories):

    categories_intention_scores = {}
    categories_yes_codes = {}
    for stakeholder in stakeholders:
        categories_intention_scores[stakeholder] = {}
        categories_yes_codes[stakeholder] = {}
        for category in intention_categories[stakeholder]:
            (categories_intention_scores[stakeholder][category],
                categories_yes_codes[stakeholder][category]) = (
                category_intention_score(
                    stakeholder,
                    category, survey_scores, survey_scores_actions,
                    intention_categories
                )
            )

    return categories_intention_scores, categories_yes_codes


def intention_score(
        stakeholder,
        time, yes, model_coefficients):

    intention_categories = model_coefficients['intention_categories']
    survey_scores_actions = model_coefficients['survey_scores_actions']
    stakeholders = model_coefficients['stakeholders']
    category_weights = model_coefficients['category_weights']
    categories_intention_scores = (
        model_coefficients['categories_intention_scores']
    )
    categories_yes_codes = (
        model_coefficients['categories_yes_codes']
    )

    intention_score = {}
    for action in survey_scores_actions:
        action_intention_score = 0
        for category, weight in zip(
                intention_categories[stakeholder],
                category_weights[stakeholder]):
            yes_codes = categories_yes_codes[stakeholder][category][action]
            yes_factors = (
                [
                    yes_factor(yes_code, yes, stakeholders)
                    for yes_code in yes_codes
                ]
            )

            action_intention_score += (
                sum(
                    categories_intention_scores[stakeholder][category][action]
                    * yes_factors
                    ) * weight
                )
        intention_score[action] = action_intention_score

    return intention_score


def yes_factor(yes_code, yes, stakeholders):
    no = [1-this_yes for this_yes in yes]
    constant = [1] * len(yes)
    yes_type = yes_code.split('_')[0]
    stakeholder = yes_code.split('_')[1]
    yes_factor = locals()[yes_type][stakeholders.index(stakeholder)]
    return yes_factor


if __name__ == '__main__':
    time_start = datetime.datetime.now()
    print((datetime.datetime.now()-time_start).total_seconds())
