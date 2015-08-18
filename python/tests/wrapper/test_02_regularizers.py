import os
import itertools
import tempfile
import shutil
import pytest

import artm.wrapper
import artm.wrapper.messages_pb2 as messages
import helpers

def test_func():
    # Set some constants
    dictionary_name = 'dictionary'
    pwt = 'pwt'
    nwt = 'nwt'
    rwt = 'rwt'
    docword = 'docword.kos.txt'
    vocab = 'vocab.kos.txt'

    smsp_phi_tau = -0.2
    smsp_theta_tau = -0.1
    decor_phi_tau = 1000000

    num_topics = 10
    num_inner_iterations = 10
    num_outer_iterations = 8

    perplexity_tol = 0.001
    expected_perplexity_value_on_iteration = {
        0: 6703.161,
        1: 2426.277,
        2: 2276.476,
        3: 1814.072,
        4: 1742.911,
        5: 1637.142,
        6: 1612.946,
        7: 1581.725
    }
    sparsity_tol = 0.001
    expected_phi_sparsity_value_on_iteration = {
        0: 0.059,
        1: 0.120,
        2: 0.212,
        3: 0.306,
        4: 0.380,
        5: 0.438,
        6: 0.483,
        7: 0.516
    }
    expected_theta_sparsity_value_on_iteration = {
        0: 0.009,
        1: 0.036,
        2: 0.146,
        3: 0.239,
        4: 0.278,
        5: 0.301,
        6: 0.315,
        7: 0.319
    }

    batches_folder = tempfile.mkdtemp()
    try:
        # Create the instance of low-level API and helper object
        lib = artm.wrapper.LibArtm()
        helper = helpers.TestHelper(lib)
        
        # Parse collection from disk
        helper.parse_collection_uci(os.path.join(os.getcwd(), docword),
                                    os.path.join(os.getcwd(), vocab),
                                    batches_folder,
                                    dictionary_name)

        # Create master component and scores
        scores = [('Perplexity', messages.PerplexityScoreConfig()),
                  ('SparsityPhi', messages.SparsityPhiScoreConfig()),
                  ('SparsityTheta', messages.SparsityThetaScoreConfig()),
                  ('TopTokens', messages.TopTokensScoreConfig())]
        helper.master_id = helper.create_master_component(scores=scores)

        # Import the collection dictionary
        helper.import_dictionary(os.path.join(batches_folder, dictionary_name), dictionary_name)

        # Configure basic regularizers
        helper.create_smooth_sparse_phi_regularizer('SmoothSparsePhi')
        helper.create_smooth_sparse_theta_regularizer('SmoothSparseTheta')
        helper.create_decorrelator_phi_regularizer('DecorrelatorPhi')

        # Initialize model
        helper.initialize_model(pwt, num_topics, source_type='dictionary', dictionary_name=dictionary_name)

        for iter in xrange(num_outer_iterations):
            # Invoke one scan of the collection, regularize and normalize Phi
            helper.process_batches(pwt=pwt,
                                   nwt=nwt,
                                   num_inner_iterations=num_inner_iterations,
                                   batches_folder=batches_folder,
                                   regularizer_name=['SmoothSparseTheta'],
                                   regularizer_tau=[smsp_theta_tau])
            helper.regularize_model(pwt, nwt, rwt,
                                    ['SmoothSparsePhi', 'DecorrelatorPhi'], [smsp_phi_tau, decor_phi_tau])
            helper.normalize_model(pwt, nwt, rwt)   

            # Retrieve scores
            perplexity_score = helper.retrieve_score(pwt, 'Perplexity')
            sparsity_phi_score = helper.retrieve_score(pwt, 'SparsityPhi')
            sparsity_theta_score = helper.retrieve_score(pwt, 'SparsityTheta')

            # Assert and print scores
            print_string = 'Iter#{0}'.format(iter)
            print_string += ': Perplexity = {0:.3f}'.format(perplexity_score.value)
            print_string += ', Phi sparsity = {0:.3f}'.format(sparsity_phi_score.value)
            print_string += ', Theta sparsity = {0:.3f}'.format(sparsity_theta_score.value)
            print print_string

            assert abs(perplexity_score.value - expected_perplexity_value_on_iteration[iter]) < perplexity_tol
            assert abs(sparsity_phi_score.value - expected_phi_sparsity_value_on_iteration[iter]) < sparsity_tol
            assert abs(sparsity_theta_score.value - expected_theta_sparsity_value_on_iteration[iter]) < sparsity_tol

        # Retrieve and print top tokens score
        top_tokens_score = helper.retrieve_score(pwt, 'TopTokens')

        print 'Top tokens per topic:'
        top_tokens_triplets = zip(top_tokens_score.topic_index, zip(top_tokens_score.token, top_tokens_score.weight))
        for topic_index, group in itertools.groupby(top_tokens_triplets, key=lambda (topic_index, _): topic_index):
            print_string = 'Topic#{0} : '.format(topic_index)
            for _, (token, weight) in group:
                print_string += ' {0}({1:.3f})'.format(token, weight)
            print print_string
    finally:
        shutil.rmtree(batches_folder)
