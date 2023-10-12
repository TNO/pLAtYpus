import matplotlib.pyplot as plt

import pandas as pd

from ETS_CookBook import ETS_CookBook as cook

parameters_file_name = 'pLAtYpus.toml'
parameters = cook.parameters_from_TOML(parameters_file_name)

output_folder = 'output'
file_root = 'Intention Weights'

products = [
    'autonomous_cars', 'sustainable_transport', 'cooperative_self_generation'
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


plt.savefig('output/Intention Weights.png', bbox_inches='tight')
plt.savefig('output/Intention Weights.svg', bbox_inches='tight')
