# imgsearch

This repository provide a simple program for exporting a set of signatures,
which desribe patches of image data into a format that can be ingeted into
google cloud and queried using a cloud function.  The goal is to enable
one to quickly do image searche over a large image dataset (such as
an electron microscopy, EM, dataset).

The program enables fast querying by hashing the signatures into different
non-overlapping partitions of their bit space.  In this manner, exact
hash lookups can be done in each partition, and matches within a certain
hamming distance are guaranteed to be found.


## Installation

To install the C++ script

	%  g++ -std=c++11 -o process_signatures process_signatures.cpp

The python function is actually installed by copying
in the [clio_toplevel](https://github.com/janelia-flyem/clio_toplevel)
google cloud function deployment.

## Running

To process a binary file with x,y,z, coordinates of 4 bytes each
followed by an 8 byte signature, call:

	% ./process_signatures <binary file> <# max match> <super block size>

The #max match is the number of identical signatures that will be used
in the fast look-ups.  A limit is recommended (such as 100) to avoid
pathologicaal cases where a significant portion of signatures are identical
and are saved into the same hash bin.  The super block size
is the block size used to group x,y,z signatures into the same file.  One
should choose a block size that groups at least 1000 coordinates together.
Grouping too many coordinates together will lead to decreased performance
for x,y,z lookups.

The result of this program is a set of files saved in 'data_out'.  This
directory should be copied into a Google storage bucket
that is pointed to by the python function environment variable and into
a directory named after the corresponding dataset.

The /hamming_[0123] tables should be loaded as separate tables in a BigQuery
dataset named "DATASET_imgsearch".  The first field of the CSVs is the partition
id, which should be used to boost the performance of searches in BigQuery.

## TODO

* expand cloud function API for programmatic access (query multiple points, batch access)
* provide API to view pre-computed clusters
