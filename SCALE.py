#!/usr/bin/env python
"""
# Author: Xiong Lei
# Created Time : Sat 28 Apr 2018 08:31:29 PM CST

# File Name: SCALE.py
# Description: Single-Cell ATAC-seq Analysis via Latent feature Extraction.
    Input: 
        scATAC-seq data
    Output:
        1. latent GMM feature
        2. cluster assignment
        3. imputation data
"""


import time
import torch

import numpy as np
import pandas as pd
import argparse

from scale import SCALE
from scale.utils import read_labels, get_loader, save_results, cluster_report
from scale import config


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='SCALE: Single-Cell ATAC-seq Analysis via Latent feature Extraction')
    parser.add_argument('--data', '-d', type=str, help='input data matrix peaks x samples')
    parser.add_argument('--n_centroids', '-k', type=int, help='cluster number')
    parser.add_argument('--sep', type=str, default='\t', help='input data sep format \t or , ')
    parser.add_argument('--outdir', '-o', type=str, default='output/', help='Output path')
    parser.add_argument('--no_results', action='store_true', help='Not Save the results')
    parser.add_argument('--verbose', action='store_false', help='Print loss of training process')
    parser.add_argument('--reference', '-r', type=str, default='', help='Whether ground truth available')
    parser.add_argument('--pretrain', type=str, default=None, help='Load the trained model')
    parser.add_argument('--epochs', '-e', type=int, default=None, help='Training epochs')
    parser.add_argument('--lr', type=float, default=None, help='Learning rate')
    parser.add_argument('--batch_size', '-b', type=int, default=None, help='Batch size')
    parser.add_argument('--device', default='cuda', help='Use gpu when training')
    parser.add_argument('--seed', type=int, default=18, help='Random seed for repeat results')
    parser.add_argument('--input_dim', type=int, default=None, help='Force input dim')
    parser.add_argument('--log_transform', action='store_true', help='Perform log2(x+1) transform')
    parser.add_argument('--gene_filter', action='store_true', help='Perform gene filter as SC3')
    parser.add_argument('-x', '--pct', type=float, default=6, help='Percent of genes when performing gene filter as SC3')

    args = parser.parse_args()

    # Set random seed
    seed = args.seed
    np.random.seed(seed)
    torch.manual_seed(seed)

    args.device = args.device if torch.cuda.is_available() and args.device!="cpu" else "cpu" 
    device = torch.device(args.device)
    if args.batch_size is None:
        batch_size = config.batch_size
    else:
        batch_size = args.batch_size

    # Load data and labels
    data_params_ = get_loader(args.data, 
                              args.input_dim, 
                              sep=args.sep,
                              batch_size=batch_size, 
                              X=args.pct,
                              gene_filter=args.gene_filter,
                              log_transform=args.log_transform)
    dataloader, data, data_params = data_params_[0], data_params_[1], data_params_[2:]
    cell_num = data.shape[0] 
    input_dim = data.shape[1] 	

    k = args.n_centroids

    if args.epochs is None:
        epochs = config.epochs
    else:
        epochs = args.epochs
    if args.lr is None:
        lr = config.lr
    else:
        lr = args.lr

    print("\n**********************************************************************")
    print("  SCALE: Single-Cell ATAC-seq analysis via Latent feature Extraction")
    print("**********************************************************************\n")
    print("======== Parameters ========")
    print('Cell number: {}\nInput_dim: {}\nn_centroids: {}\nEpoch: {}\nSeed: {}\nDevice: {}'.format(
        cell_num, input_dim, k, epochs, args.seed, args.device))
    print("============================")

    dims = [input_dim, config.latent, config.encode_dim, config.decode_dim]
    model = SCALE(dims, n_centroids=k, device=device)
    model.to(device)
    data = data.to(device)
    if not args.pretrain:
        print('\n## Training Model ##')
        t0 = time.time()
        model.init_gmm_params(data)
        model.fit(dataloader,
                  lr=lr, 
                  weight_decay=config.weight_decay, 
                  epochs=epochs, 
                  verbose=args.verbose,
                  print_interval=config.print_interval
                   )
        print('\nRunning Time: {:.2f} s'.format(time.time()-t0))
    else:
        print('\n## Loading Model {} ##\n'.format(args.pretrain))
        model.load_model(args.pretrain)

    # Clustering Report
    if args.reference:
        ref, classes = read_labels(args.reference)
        pred = model.predict(data)
        cluster_report(ref, pred, classes)

    outdir = args.outdir
    if not args.no_results:
        save_results(model, data, data_params, args.outdir)

