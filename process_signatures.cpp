/* Simple script to read signatures corresponding to patches of an image and produce a
 * set of files that can be easily mined.
 *
 * Building: g++ -std=c++11 -o process_signatures process_signatures.cpp
 * Usage: <prog> <signature file> <# max match> <super block size>
 *
 * The signature file is just x,y,z,signature repeating.  4 bytes for each
 * x, y, and z and 8 bytes for the signature
 *
 * Output: Files in "data_out/" directory.  "info.json" with informataion on
 * the signatures.  "blocks/" gives all the signatures grouped by contiguous
 * chunks.  "hamming_[0123]/sigs_[0...]" gives a list of signatures for
 * each hamming partition.
*/

#include <iostream>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <array>
#include <bitset>
#include <string>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <random> 
#include <numeric>
#include <cassert>

using std::unordered_map; using std::vector; using std::hash; using std::array; using std::unordered_set;
using std::cout; using std::endl; using std::ifstream; using std::stringstream; using std::ofstream;
using std::string;
using std::bitset;
using std::shuffle;

// could redefine Sig_t to 32 bit as well
const size_t NUM_BITS = 64; // must be a multiple of 8
const size_t PARTITIONS = 4000;
typedef uint64_t Sig_t;


// maximum rows in CSV file
const size_t MAX_ENTRIES = 1000000;

// other constants 
// bit width for hashing signatures together
const size_t HASH_BITS = 16;

// number of bits to split signature
const size_t HAMMING_BITS = 16;


// other typedefs
typedef Sig_t HashSig_t;
typedef Sig_t HamSig_t;
typedef array<uint32_t, 3> Point3D_t;
typedef std::string Point3D_str_t;
typedef unordered_map<Sig_t, vector<Point3D_t > > sig2match_t; 
typedef std::pair<Sig_t, Point3D_t> SigLoc_t;
typedef unordered_map<HamSig_t, unordered_set<Sig_t> > partial_match_t;

/* Adapted from murmur64 example on
 * https://lemire.me/blog/2018/08/15/fast-strongly-universal-64-bit-hashing-everywhere
*/
uint64_t murmur64(uint64_t h) {
    h ^= h >> 33;
	h *= 0xff51afd7ed558ccdL;
	h ^= h >> 33;
	h *= 0xc4ceb9fe1a85ec53L;
	h ^= h >> 33;
	return h;
}


/*
 * command: <signature file> (x,y,z,sig...)  <# max match> <super block size>
*/ 
int main(int argc, char** argv) {
    // read args -- get total number of signatures
    if (argc != 4) {
        cout << "Usage:  <program> <file> <#max match> <super block size>" << endl;
	   	exit(-1);	
    }
    string filename = argv[1];
    size_t max_match = atoi(argv[2]);
    size_t sblock_size = atoi(argv[3]);

    assert((NUM_BITS % 8) == 0);
	assert((NUM_BITS % HASH_BITS) == 0);

	// superblock hash
	unordered_map<Point3D_str_t, vector<SigLoc_t> >  block_signatures;

    // locations for a signature (will be limited to <= # max match)
	sig2match_t  signatures;
	
	// create masks
    vector<Sig_t> sig_hash_masks;
    int num_masks = NUM_BITS / HASH_BITS;

	// use bitset to make hamming sigs -- randomize 64 numbers and set bits in each 16bit section
	vector<int> random_array;
	for (int i = 0; i < NUM_BITS; i++) {
		random_array.push_back(i);
	}
	shuffle(random_array.begin(), random_array.end(), std::default_random_engine(0));
	int rand_spot = 0;
	for (int i = 0; i < num_masks; ++i) {
			bitset<NUM_BITS> sigbits;
			for (int j = 0; j < HASH_BITS; ++j) {
				sigbits.set(random_array[rand_spot], true);
				++rand_spot;
			}
			sig_hash_masks.push_back(sigbits.to_ulong());
	}


    // iterate file and load structures
	ifstream fin(filename, std::ios_base::binary|std::ios_base::in);
    while(fin) {
        uint32_t x, y, z;
        fin.read((char*) &x, sizeof(uint32_t));
        fin.read((char*) &y, sizeof(uint32_t));
        fin.read((char*) &z, sizeof(uint32_t));
        
        Point3D_t cpoint = {x,y,z};
        
        // superblock hash
        uint32_t xb, yb, zb;
        xb = x / sblock_size;
        yb = y / sblock_size;
        zb = z / sblock_size;

        stringstream sblock_index;
        sblock_index << x / sblock_size  << "_" << y / sblock_size << "_" << z / sblock_size; 

        // set signature
        Sig_t sig;
        fin.read((char*) &sig, sizeof(Sig_t));

        // save to super block
        block_signatures[sblock_index.str()].push_back(SigLoc_t(sig, cpoint));

		signatures[sig].push_back(cpoint);
    }

	string outdir("data_out");

	// write out a CSV table for each hamming bin
	for (int mask = 0; mask < num_masks; ++mask) {
		string prefix = outdir + "/hamming" + std::to_string(mask) + "/"; 
		vector<int> sig_collisions(PARTITIONS);

		int num_entries = 0;
		
		string mkdir_command = string("mkdir -p ") + prefix;
		std::system(mkdir_command.c_str()); 
		ofstream fout(prefix + "sigs_" + std::to_string(num_entries / MAX_ENTRIES) );
		//fout << "part,signature,x,y,z\n";

		for (auto iter = signatures.begin(); iter != signatures.end(); ++iter) {
			size_t total_sigs = iter->second.size();
			if (total_sigs > max_match) {
				shuffle (iter->second.begin(), iter->second.end(), std::default_random_engine(0));
				total_sigs = max_match;
			}

			// write csv row
			size_t partition_id = murmur64(iter->first & sig_hash_masks[mask]) % PARTITIONS;
			
			for (int i = 0; i < total_sigs; ++i) {
				++num_entries;
				sig_collisions[partition_id] += 1; 

				Point3D_t xyz = iter->second[i];
				fout << partition_id  << "," << int64_t(iter->first) << ",";
				fout << xyz[0] << "," << xyz[1] << "," << xyz[2] << "\n";
				
				// split into multiple files	
				if ((num_entries % MAX_ENTRIES) == 0) {
						fout.close();
						fout.open(prefix + "sigs_" + std::to_string(num_entries / MAX_ENTRIES) );
						//fout << "part,signature,x,y,z\n";
				}
			} 
		
		}
		fout.close();
	
		// print out bin distribution stats
		cout << "Ham-" << mask << ": " << *std::min_element(sig_collisions.begin(), sig_collisions.end());
		cout << ", " << *std::max_element(sig_collisions.begin(), sig_collisions.end());
		cout << ", " << std::accumulate(sig_collisions.begin(), sig_collisions.end(), 0)/sig_collisions.size() << endl; 
	}
	
	string mkdir_command = string("mkdir -p ") + outdir + "/blocks/";
	std::system(mkdir_command.c_str()); 
	for (auto iter = block_signatures.begin(); iter != block_signatures.end(); ++iter) {
		ofstream fout(outdir + "/blocks/" + iter->first, std::ios_base::binary|std::ios_base::out);

		for (auto iter2 = iter->second.begin(); iter2 != iter->second.end(); ++iter2) {
			fout.write((char*) &(iter2->second[0]), sizeof(uint32_t));
			fout.write((char*) &(iter2->second[1]), sizeof(uint32_t));
			fout.write((char*) &(iter2->second[2]), sizeof(uint32_t));
			fout.write((char*) &(iter2->first), sizeof(Sig_t));
		}

		fout.close();
	}

    // make a config file with mask signatures
    ofstream fout(outdir + "/info.json");
    fout << "{";
    for (int i = 0; i < num_masks; ++i) {
        fout << "\"ham_" << i << "\": \"" << sig_hash_masks[i] << "\",";
    }
    fout << "\"block_size\":" << sblock_size << ", \"num_bits\":" << NUM_BITS << " }";
    fout.close();

}
