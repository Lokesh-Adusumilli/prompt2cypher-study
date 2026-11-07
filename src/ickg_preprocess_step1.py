import pandas as pd
import os

data_dir = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/ionchan_24_05_29/'
preprocced_dir = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/ionchan_24_05_29/preprocessed/'

# make directory for preprocessed files if it doesn't exist
if not os.path.exists(preprocced_dir):
    os.makedirs(preprocced_dir)

def remove_newline_characters(df):
    for column in df.columns:
        df[column] = df[column].astype(str).str.replace('\n', ' ').str.replace('\r', ' ')
    return df

# Load the data
print("Load the data")
df_nodes = pd.read_csv(f'{data_dir}df_node.csv')
df_nodes = remove_newline_characters(df_nodes) # Data cleaning (remove newline characters)

df_edges = pd.read_csv(f'{data_dir}df_edges.csv', low_memory=False)
df_types = pd.read_csv(f'{data_dir}df_type.csv')
df_relations = pd.read_csv(f'{data_dir}df_relation.csv')

# Create dictionaries to map ids to names
print("Create dictionaries to map ids to names")
# via astype(str) above, turning integer type_id/r_id values into strings like '0','1'...
# int-keyed dicts would silently produce NaN for every row without this fix.
type_dict = {str(k): v for k, v in df_types.set_index('id')['name'].to_dict().items()}
relation_dict = {str(k): v for k, v in df_relations.set_index('id')['name'].to_dict().items()}

# Replace type_id with type name in df_nodes
print("Replace type_id with type name in df_nodes")
df_nodes['type'] = df_nodes['type_id'].map(type_dict)
df_nodes = df_nodes.drop(columns=['type_id'])

# Replace r_id with relation name in df_edges
print("Replace r_id with relation name in df_edges")
df_edges['relation'] = df_edges['r_id'].map(relation_dict)
df_edges = df_edges.drop(columns=['r_id'])

# Save the preprocessed files
print("Save the preprocessed files")
nodes_file = f'{preprocced_dir}df_node_preprocessed_step1.csv'
edges_file = f'{preprocced_dir}df_edges_preprocessed_step1.csv'
df_nodes.to_csv(nodes_file, index=False)
df_edges.to_csv(edges_file, index=False)

print(f"Preprocessed files saved to {nodes_file} and {edges_file}. Now, run step 2.")