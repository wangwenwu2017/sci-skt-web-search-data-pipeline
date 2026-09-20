"""A real Data Designer custom processing step; no model API required."""
import argparse

import data_designer.config as dd


@dd.custom_column_generator(required_columns=["a", "b"])
def add(row: dict) -> dict:
    row["c"] = row["a"] + row["b"]
    return row


def load_config_builder(params=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-path", default="examples/arithmetic/seeds.jsonl")
    args = parser.parse_args(list(params.argv if params else ()))
    builder = dd.DataDesignerConfigBuilder()
    builder.with_seed_dataset(dd.LocalFileSeedSource(path=args.seed_path))
    builder.add_column(dd.CustomColumnConfig(name="c", generator_function=add))
    return builder
