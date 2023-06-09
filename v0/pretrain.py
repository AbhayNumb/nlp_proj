from collections import defaultdict
import os
import pickle
import sys

import numpy as np
from rdkit import Chem

from gensim.models import Word2Vec
import pandas as pd

def create_atoms(mol):
    """Create a list of atom (e.g., hydrogen and oxygen) IDs
    considering the aromaticity."""
    atoms = [a.GetSymbol() for a in mol.GetAtoms()]
    for a in mol.GetAromaticAtoms():
        i = a.GetIdx()
        atoms[i] = (atoms[i], 'aromatic')
    atoms = [atom_dict[a] for a in atoms]
    return np.array(atoms,dtype=object)


def create_ijbonddict(mol):
    """Create a dictionary, which each key is a node ID
    and each value is the tuples of its neighboring node
    and bond (e.g., single and double) IDs."""
    i_jbond_dict = defaultdict(lambda: [])
    for b in mol.GetBonds():
        i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
        bond = bond_dict[str(b.GetBondType())]
        i_jbond_dict[i].append((j, bond))
        i_jbond_dict[j].append((i, bond))
    return i_jbond_dict


def extract_fingerprints(atoms, i_jbond_dict, radius):
    """Extract the r-radius subgraphs (i.e., fingerprints)
    from a molecular graph using Weisfeiler-Lehman algorithm."""
    if (len(atoms) == 1) or (radius == 0):
        fingerprints = [fingerprint_dict[a] for a in atoms]
    else:
        nodes = atoms
        i_jedge_dict = i_jbond_dict
        for _ in range(radius):
            """Update each node ID considering its neighboring nodes and edges
            (i.e., r-radius subgraphs or fingerprints)."""
            fingerprints = []
            for i, j_edge in i_jedge_dict.items():
                neighbors = [(nodes[j], edge) for j, edge in j_edge]
                fingerprint = (nodes[i], tuple(sorted(neighbors)))
                fingerprints.append(fingerprint_dict[fingerprint])
            nodes = fingerprints
            """Also update each edge ID considering two nodes
            on its both sides."""
            _i_jedge_dict = defaultdict(lambda: [])
            for i, j_edge in i_jedge_dict.items():
                for j, edge in j_edge:
                    both_side = tuple(sorted((nodes[i], nodes[j])))
                    edge = edge_dict[(both_side, edge)]
                    _i_jedge_dict[i].append((j, edge))
            i_jedge_dict = _i_jedge_dict
    return np.array(fingerprints,dtype=object)


def create_adjacency(mol):
    adjacency = Chem.GetAdjacencyMatrix(mol)
    return np.array(adjacency,dtype=object)


def seq_to_kmers(seq, k=3):
    """ Divide a string into a list of kmers strings.

    Parameters:
        seq (string)
        k (int), default 3
    Returns:
        List containing a list of kmers.
    """
    N = len(seq)
    return [seq[i:i+k] for i in range(N - k + 1)]

def get_protein_embedding(model,protein):
    """get protein embedding,infer a list of 3-mers to (num_word,100) matrix"""
    vec = np.zeros((len(protein), 101))
    i = 0
    l = len(protein)
    for word in protein:
        vec[i, ] = np.append(model.wv[word],float(i+1)/float(l))
        i += 1
    return vec


def dump_dictionary(dictionary, filename):
    with open(filename, 'wb') as f:
        pickle.dump(dict(dictionary), f)


if __name__ == "__main__":

    radius, ngram = 2,3
    radius, ngram = map(int, [radius, ngram])

    with open('./input/celegansCopy.txt', 'r') as f:
        data_list = f.read().strip().split('\n')

    """Exclude data contains '.' in the SMILES format."""
    data_list = [d for d in data_list if '.' not in d.strip().split()[0]]
    N = len(data_list)

    atom_dict = defaultdict(lambda: len(atom_dict))
    bond_dict = defaultdict(lambda: len(bond_dict))
    fingerprint_dict = defaultdict(lambda: len(fingerprint_dict))
    edge_dict = defaultdict(lambda: len(edge_dict))
    model = Word2Vec.load("./input/word2vec_100.model")

    Smiles, compounds, adjacencies, proteins, interactions = '', [], [], [], []

    for no, data in enumerate(data_list):
        print('/'.join(map(str, [no+1, N])))
        smiles, sequence, interaction = data.strip().split()
        Smiles += smiles + '\n'
        mol = Chem.AddHs(Chem.MolFromSmiles(smiles))  # Consider hydrogens.
        atoms = create_atoms(mol)
        i_jbond_dict = create_ijbonddict(mol)
        fingerprints = extract_fingerprints(atoms, i_jbond_dict, radius)
        compounds.append(fingerprints)
        adjacency = create_adjacency(mol)#MATRIX of smiles
        adjacencies.append(adjacency)
        proteins.append(get_protein_embedding(model,seq_to_kmers(sequence)))
        interactions.append(([float(interaction)]))#0 or 1 
        # print(interaction)
    dir_input = ('./input/celegansCopy/'
             'radius' + str(radius) + '_ngram' + str(ngram) + '/')
    os.makedirs(dir_input, exist_ok=True)

    with open(dir_input + 'Smiles.txt', 'w') as f:
        f.write(Smiles)


    np.save(dir_input + 'compounds', compounds)
    np.save(dir_input + 'adjacencies', adjacencies)
    np.save(dir_input + 'proteins', proteins)
    np.save(dir_input + 'interactions', interactions)
    dump_dictionary(fingerprint_dict, dir_input + 'fingerprint_dict.pickle')