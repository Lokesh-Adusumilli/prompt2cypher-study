import pandas as pd
import glob
from goatools.obo_parser import GODag
import requests
import os
import time

data_path = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/ionchan_24_05_29/'
preprocessed_dir = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/ionchan_24_05_29/preprocessed/'
reactome_path = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/DataMappingKG/UniProt2Reactome_All_Levels.txt'
go_ontology_path = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/DataMappingKG/go-basic.obo'
excel_path = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/Human_Ion_channel_.xlsx'
uniprot_path = '/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/DataMappingKG/'

def merge_uniprot_data():
    print("Loading Uniprot data from TSV files")
    uniprot_files = glob.glob(f'{uniprot_path}/*.tsv')
    uniprot_df_list = [pd.read_csv(file, sep='\t') for file in uniprot_files]
    
    df_uniprot = pd.concat(uniprot_df_list, ignore_index=True)
    df_uniprot['Entry Name'] = df_uniprot['Gene Names'].str.split(' ').str[0]  # Remove Codes
    uniprot_dict = df_uniprot.set_index('Entry')['Gene Names'].to_dict()

    print("Loading data from Excel file")
    df_excel = pd.read_excel(excel_path, usecols=['uniprot', 'symbol'])
    excel_dict = df_excel.set_index('uniprot')['symbol'].to_dict()
    uniprot_dict.update(excel_dict)
    
    print("Loading data from CSV file")
    df_csv = pd.read_csv('/home/lokeshadusumilli/Downloads/ionchannels/ionchannels/kg/DataMappingKG/kinase_human.csv')
    csv_dict = df_csv.set_index('uniprot_id')['gene'].to_dict()
    uniprot_dict.update(csv_dict)

    return uniprot_dict

uniprot_dict = merge_uniprot_data()

types_with_uniprot_ids = ['Protein', 'LightKinase', 'LightIonChannel', 'DarkKinase', 'DarkIonChannel']

def print_report(data_type, labels_before, labels_after):
    affected = (labels_before != labels_after).sum()
    not_affected = labels_after.isna().sum()
    
    print(f'{data_type} data labels affected: {int(affected)}')
    print(f'{data_type} data labels not affected: {int(not_affected)}')
    print("\n------\n")

def load_data():
    print("Loading nodes and edges")
    df_nodes = pd.read_csv(f'{data_path}df_node_preprocessed_step1.csv')
    # Define label column with NaN default value
    df_nodes['label'] = pd.NA

    df_edges = pd.read_csv(f'{data_path}df_edges_preprocessed_step1.csv', low_memory=False)
    return df_nodes, df_edges

def apply_reactome_labels(df_nodes):
    print("Loading Reactome data")
    df_reactome = pd.read_csv(reactome_path, sep='\t', header=None, names=['uniprot_id', 'reactome_id', 'url', 'description', 'evidence', 'species'])
    df_reactome = df_reactome[df_reactome['reactome_id'].str.contains('R-HSA-')]
    df_reactome['reactome_id'] = df_reactome['reactome_id'].str.replace('R-HSA-', '')
    reactome_dict = df_reactome.set_index('reactome_id')['description'].to_dict()

    mask = df_nodes['type'] == 'Pathway'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].map(reactome_dict)
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Pathway", labels_before, labels_after)
    
    return df_nodes

# def apply_go_ontology_labels(df_nodes):
#     print("Loading GO Ontology data")
#     go_dag = GODag(go_ontology_path)
#     go_dict = {term.id: term.name for term in go_dag.values()}
    
#     types = ['BiologicalProcess', 'MolecularFunction', 'CellularComponent']
#     mask = df_nodes['type'].isin(types)
#     labels_before = df_nodes.loc[mask, 'label'].copy()
#     df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].map(go_dict)
#     labels_after = df_nodes.loc[mask, 'label']
#     print_report("Go Ontology", labels_before, labels_after)
#     return df_nodes

# def apply_go_ontology_labels_api(df_nodes, cache_file=f'{preprocessed_dir}go_labels_cache.csv', batch_size=100):
#     panther_api_endpoint = "https://pantherdb.org/services/oai/pantherdb/search?"
#     go_ids = [id.split(':')[-1] for id in df_nodes[df_nodes['type'].isin(['BiologicalProcess', 'MolecularFunction', 'CellularComponent'])]['name'].tolist()]
#     ...

def apply_go_ontology_labels(df_nodes):
    print("Loading GO Ontology data from local OBO file")
    go_dag = GODag(go_ontology_path)
    go_dict = {term.id: term.name for term in go_dag.values()}

    types = ['BiologicalProcess', 'MolecularFunction', 'CellularComponent']
    mask = df_nodes['type'].isin(types)
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].map(go_dict)
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Go Ontology", labels_before, labels_after)
    return df_nodes

def apply_uniprot_labels(df_nodes):
    mask = df_nodes['type'].isin(types_with_uniprot_ids)
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].map(uniprot_dict)
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Uniprot", labels_before, labels_after)

    return df_nodes

def apply_ptm_labels(df_nodes):
    mask = df_nodes['type'] == 'PTM'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes.loc[mask, 'name'].apply(lambda x: x.split('_')[-1]).map(uniprot_dict).combine_first(
        df_nodes.loc[mask, 'name'].apply(lambda x: x.split('_')[-1]).map(uniprot_dict)
    )
    labels_after = df_nodes.loc[mask, 'label']
    print_report("PTM", labels_before, labels_after)
    return df_nodes

def apply_general_labels(df_nodes):
    mask = df_nodes['type'] == 'Family'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].str.split('_').str[0]
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Family", labels_before, labels_after)

    mask = df_nodes['type'] == 'Group'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].str.split('_').apply(lambda x: ' '.join(x[:-1]))
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Group", labels_before, labels_after)

    mask = df_nodes['type'] == 'GateMechanism'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name']
    labels_after = df_nodes.loc[mask, 'label']
    print_report("GateMechanism", labels_before, labels_after)

    mask = df_nodes['type'] == 'Ion'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name']
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Ion", labels_before, labels_after)

    mask = df_nodes['type'] == 'IonChannelUnit'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name']
    labels_after = df_nodes.loc[mask, 'label']
    print_report("IonChannelUnit", labels_before, labels_after)

    mask = df_nodes['type'] == 'FunctionalDomain'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name']
    labels_after = df_nodes.loc[mask, 'label']
    print_report("FunctionalDomain", labels_before, labels_after)

    return df_nodes


def apply_disease_labels(df_nodes, cache_file=f'{preprocessed_dir}disease_labels_cache.csv', batch_size=100):
    # Define the SPARQL endpoint URL
    sparql_endpoint = "https://id.nlm.nih.gov/mesh/sparql"

    # Extract MeSH IDs from df_nodes of type 'Disease' and remove "MESH:" prefix
    disease_ids = [id.split(':')[-1] for id in df_nodes[df_nodes['type'] == 'Disease']['name'].tolist()]

    # Load existing cache
    if os.path.exists(cache_file):
        cache_df = pd.read_csv(cache_file)
        cache_dict = cache_df.set_index('disease_id')['label'].to_dict()
    else:
        cache_dict = {}

    # Determine which IDs need to be queried
    mesh_ids_to_query = [id for id in disease_ids if id not in cache_dict]
    mesh_ids = [f"mesh:{id}" for id in mesh_ids_to_query]

    # Function to process a batch of mesh_ids
    def fetch_labels_for_batch(batch):
        query = f"""
        PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?id ?label
        WHERE {{
            VALUES ?id {{ {' '.join(batch)} }}
            ?id rdfs:label ?label .
        }}
        """

        headers = {
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {
            "query": query
        }

        response = requests.post(sparql_endpoint, headers=headers, data=payload)

        if response.status_code == 200:
            results = response.json()
            return {result['id']['value'].split('/')[-1]: result['label']['value'] for result in results['results']['bindings']}
        else:
            print(f"Error fetching disease labels: {response.status_code}")
            return {}

    # Process all mesh_ids in batches and update cache
    new_labels = {}
    for i in range(0, len(mesh_ids), batch_size):
        batch = mesh_ids[i:i + batch_size]
        batch_labels = fetch_labels_for_batch(batch)
        new_labels.update(batch_labels)
        
        # Update cache_dict with new labels
        cache_dict.update(batch_labels)
        
        # Save updated cache to file after each batch
        cache_df = pd.DataFrame(list(cache_dict.items()), columns=['disease_id', 'label'])
        cache_df.to_csv(cache_file, index=False)
        
        time.sleep(3)
        print(f"Processed {i + len(batch)}/{len(mesh_ids)} disease labels")

    # Update the labels in df_nodes
    mask = df_nodes['type'] == 'Disease'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].apply(lambda x: x.split(':')[-1]).map(cache_dict)
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Disease", labels_before, labels_after)

    return df_nodes

def apply_chemical_labels(df_nodes):

    chemical_csv = f'{preprocessed_dir}CTD_chem_gene_ixns-Chemicals.csv'
    chemical_df = pd.read_csv(chemical_csv)
    chemical_dict = chemical_df.set_index('ChemicalID')['ChemicalName'].to_dict()

    # Update the labels in df_nodes
    mask = df_nodes['type'] == 'Chemical'
    labels_before = df_nodes.loc[mask, 'label'].copy()
    df_nodes.loc[mask & df_nodes['label'].isna(), 'label'] = df_nodes['name'].map(chemical_dict)
    labels_after = df_nodes.loc[mask, 'label']
    print_report("Chemical", labels_before, labels_after)

    return df_nodes


def save_preprocessed_files(df_nodes, df_edges):
    print("Saving the preprocessed files")
    # Ensure the 'name' column is set as the ID and 'type' as the label for nodes
    df_nodes.drop(columns=['id'], inplace=True)  # Assuming 'id' is not needed
    df_nodes.rename(columns={'name': 'name:ID', 'type': 'type:LABEL'}, inplace=True)
    df_nodes.to_csv(f'{preprocessed_dir}df_nodes_final.csv', index=False)

    # Rename columns for edges to align with Neo4j import requirements
    df_edges.rename(columns={'h': ':START_ID', 't': ':END_ID', 'r': ':TYPE'}, inplace=True)
    df_edges.to_csv(f'{preprocessed_dir}df_edges_final.csv', index=False)
    
    print(f"Preprocessed files saved to {preprocessed_dir}df_nodes_final.csv and {preprocessed_dir}df_edges_final.csv.")


if __name__ == "__main__":
    df_nodes, df_edges = load_data()
    df_nodes = apply_general_labels(df_nodes)
    df_nodes = apply_reactome_labels(df_nodes)
    df_nodes = apply_go_ontology_labels(df_nodes)
    df_nodes = apply_uniprot_labels(df_nodes)
    df_nodes = apply_ptm_labels(df_nodes)
    df_nodes = apply_disease_labels(df_nodes)
    df_nodes = apply_chemical_labels(df_nodes)  # CTD file now available
    save_preprocessed_files(df_nodes, df_edges)