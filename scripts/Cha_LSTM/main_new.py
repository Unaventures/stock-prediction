import os
from collections import defaultdict

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"
import numpy

numpy.random.seed(1)
import functools
import tensorflow as tf
import logging
import math
from tensorflow import logging  as log
from tensorflow.python import debug as tf_debug
from collections import OrderedDict
from data_iterator import TextIterator
from tensorflow.contrib import rnn
import tensorflow.contrib.layers as layers
import warnings
import pickle as pkl
import sys
import pprint
import pdb
import os
import copy
import time
import matplotlib.pyplot as plt
import pickle

logger = logging.getLogger(__name__)


def str2list(s):
    alphabet = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,;.!?:'\"/\\|_@#$%^&*~`+-=<>()[]{}"
    l = len(s)
    ans = []
    for i in range(0, l):
        a = alphabet.find(s[i])
        if a >= 0:
            ans.append(a)
        else:
            ans.append(0)
            # print(s[i])
    return ans


def str2list_v2(s, max):
    alphabet = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,;.!?:'\"/\\|_@#$%^&*~`+-=<>()[]{}"
    ans = []
    c = list(s.ljust(max))
    for i in c:
        a = alphabet.find(i)
        if a >= 0:
            ans.append(a)
        else:
            ans.append(0)
            # print(s[i])
    return ans


def _s(pp, name):  # add perfix
    return '{}_{}'.format(pp, name)


def load_params(path, params):
    pp = numpy.load(path)
    for kk, vv in params.iteritems():
        if kk not in pp:
            warnings.warn('{} is not in the archive'.format(kk))
            continue
        params[kk] = pp[kk]

    return params


def xavier_init(fan_in, fan_out, constant=1):
    low = -constant * numpy.sqrt(6.0 / (fan_in + fan_out))
    high = constant * numpy.sqrt(6.0 / (fan_in + fan_out))
    W = numpy.random.uniform(low=low, high=high, size=(fan_in, fan_out))
    return W.astype('float32')


def ortho_weight(ndim):  # used by norm_weight below
    """
    Random orthogonal weights

    Used by norm_weights(below), in which case, we
    are ensuring that the rows are orthogonal
    (i.e W = U \Sigma V, U has the same
    # of rows, V has the same # of cols)
    """
    W = numpy.random.randn(ndim, ndim)
    u, s, v = numpy.linalg.svd(W)
    return u.astype('float32')


def norm_weight(nin, nout=None, scale=0.01, ortho=True):
    """
    Random weights drawn from a Gaussian
    """
    if nout is None:
        nout = nin
    if nout == nin and ortho:
        W = ortho_weight(nin)
    else:
        # W = numpy.random.uniform(-0.5,0.5,size=(nin,nout))
        W = scale * numpy.random.randn(nin, nout)
    return W.astype('float32')


def prepare_data(sequence, sequence_d1, sequence_d2, labels, max_word_len, options, worddicts_r, maxlen=None,
                 max_word=100):
    # length = [len(s) for s in sequence]
    length, length_d1, length_d2 = [], [], []
    for i, d1, d2 in zip(sequence, sequence_d1, sequence_d2):
        dd1, dd2 = list(), list()
        length.append(len(i))
        for day in d1:
            dd1.append(len(day))
        length_d1.append(dd1)
        for day in d2:
            dd2.append(len(day))
        length_d2.append(dd2)
    if maxlen is not None:  # max length is the news level
        new_sequence = []
        new_lengths = []
        new_sequence_d1 = []
        new_lengths_d1 = []
        new_sequence_d2 = []
        new_lengths_d2 = []
        for l, s, ld1, sd1, ld2, sd2 in zip(length, sequence, length_d1, sequence_d1, length_d2, sequence_d2):
            dd1, lld1, dd2, lld2 = list(), list(), list(), list()
            if l < maxlen:
                new_sequence.append(s)
                new_lengths.append(l)
            for i, j in zip(ld1, sd1):
                if i < maxlen:
                    dd1.append(j)
                    lld1.append(i)
            new_sequence_d1.append(dd1)
            new_lengths_d1.append(lld1)
            for i, j in zip(ld2, sd2):
                if i < maxlen:
                    dd2.append(j)
                    lld2.append(i)
            new_sequence_d2.append(dd2)
            new_lengths_d2.append(lld2)

        length = new_lengths  # This step is to filter the sentence which length is bigger
        sequence = new_sequence  # than the max length. length means number of news. sequence means 
        # length of each sentence
        length_d1 = new_lengths_d1
        sequence_d1 = new_sequence_d1
        length_d2 = new_lengths_d2
        sequence_d2 = new_sequence_d2
        ##TODO need to be careful, set the max length bigger to avoid bug
        if len(length) < 1:
            return None, None, None, None, None, None, None, None
    ##TODO character level:
    max_char_len_d0 = 0
    max_char_len_d1 = 0
    max_char_len_d2 = 0
    seqs_d0_char = []
    seqs_d1_char = []
    seqs_d2_char = []
    l_seqs_d0_char = []
    l_seqs_d1_char = []
    l_seqs_d2_char = []

    for idx, (s_d0, s_d1, s_d2) in enumerate(zip(sequence, sequence_d1, sequence_d2)):
        temp_seqs_d0_char = []
        temp_l_seqs_d0_char = []
        temp_seqs_d1_char = []
        temp_l_seqs_d1_char = []
        temp_seqs_d2_char = []
        temp_l_seqs_d2_char = []
        for w_x in s_d0:
            _temp_x = []
            _temp_l_x = []
            for i in w_x:
                word = worddicts_r[i]
                word_list = str2list(word)
                l_word_list = len(word_list)
                # word_list = str2list_v2(word, max_word_len)
                # l_word_list = len(list(filter(None, word_list)))
                _temp_x.append(word_list)
                _temp_l_x.append(l_word_list)
                if l_word_list > max_word_len:
                    max_char_len_d0 = l_word_list
            temp_seqs_d0_char.append(_temp_x)
            temp_l_seqs_d0_char.append(_temp_l_x)
        for day_temp in s_d1:
            _day_temp_x = []
            _day_temp_l_x = []
            for w_x in day_temp:
                _temp_x = []
                _temp_l_x = []
                for i in w_x:
                    word = worddicts_r[i]
                    word_list = str2list(word)
                    l_word_list = len(word_list)
                    _temp_x.append(word_list)
                    _temp_l_x.append(l_word_list)
                    if l_word_list > max_word_len:
                        max_char_len_d1 = l_word_list
                _day_temp_x.append(_temp_x)
                _day_temp_l_x.append(_temp_l_x)
            temp_seqs_d1_char.append(_day_temp_x)
            temp_l_seqs_d1_char.append(_day_temp_l_x)
        for day_temp in s_d2:
            _day_temp_x = []
            _day_temp_l_x = []
            for w_x in day_temp:
                _temp_x = []
                _temp_l_x = []
                for i in w_x:
                    word = worddicts_r[i]
                    word_list = str2list(word)
                    l_word_list = len(word_list)
                    _temp_x.append(word_list)
                    _temp_l_x.append(l_word_list)
                    if l_word_list > max_word_len:
                        max_char_len_d2 = l_word_list
                _day_temp_x.append(_temp_x)
                _day_temp_l_x.append(_temp_l_x)
            temp_seqs_d2_char.append(_day_temp_x)
            temp_l_seqs_d2_char.append(_day_temp_l_x)

        seqs_d0_char.append(temp_seqs_d0_char)
        l_seqs_d0_char.append(temp_l_seqs_d0_char)
        seqs_d1_char.append(temp_seqs_d1_char)
        l_seqs_d1_char.append(temp_l_seqs_d1_char)
        seqs_d2_char.append(temp_seqs_d2_char)
        l_seqs_d2_char.append(temp_l_seqs_d2_char)
        max_char_len_d0 = max_word_len if max_char_len_d0 == 0 else max_char_len_d0
        max_char_len_d1 = max_word_len if max_char_len_d1 == 0 else max_char_len_d1
        max_char_len_d2 = max_word_len if max_char_len_d2 == 0 else max_char_len_d2

    ##TODO do the other stuff
    # day1 = len(sequence_d1[0])
    # day2 = len(sequence_d2[0])
    day1 = options['delay1'] - 1
    day2 = options['delay2'] - options['delay1']
    maxlen_x = numpy.max(length)  # max time step
    try:
        maxlen_xd1 = numpy.max([numpy.max(i) for i in length_d1])
        maxlen_xd2 = numpy.max([numpy.max(i) for i in length_d2])
    except ValueError as e:
        print(str(e))
        maxlen_xd1 = 100
        maxlen_xd2 = 100
    n_samples = len(sequence)  # number of samples== batch
    max_sequence = max(len(j) for i in sequence for j in i)  # find the sequence max length
    max_sequence_d1 = max(len(j) for i in sequence_d1 for z in i for j in z)
    max_sequence_d2 = max(len(j) for i in sequence_d2 for z in i for j in z)
    max_sequence = max_word if max_sequence > max_word else max_sequence  # shrink the data size
    max_sequence_d1 = max_word if max_sequence_d1 > max_word else max_sequence_d1  # shrink the data size
    max_sequence_d2 = max_word if max_sequence_d2 > max_word else max_sequence_d2  # shrink the data size
    ##TODO for x
    x = numpy.zeros((n_samples, maxlen_x, max_sequence)).astype('int64')
    x_mask = numpy.zeros((n_samples, maxlen_x)).astype('float32')
    char_d0 = numpy.zeros((n_samples, maxlen_x, max_sequence, max_char_len_d0)).astype('int64')
    # char_d0_mask = numpy.zeros((n_samples, maxlen_x, max_sequence)).astype('float32')
    ##TODO for x_d1
    x_d1 = numpy.zeros((n_samples, day1, maxlen_xd1, max_sequence_d1)).astype('int64')
    x_d1_mask = numpy.zeros((n_samples, day1, maxlen_xd1)).astype('float32')
    char_d1 = numpy.zeros((n_samples, day1, maxlen_xd1, max_sequence_d1, max_char_len_d1)).astype('int64')
    # char_d1_mask = numpy.zeros((n_samples, day1, maxlen_xd1, max_sequence_d1)).astype('float32')
    ##TODO for x_d2
    x_d2 = numpy.zeros((n_samples, day2, maxlen_xd2, max_sequence_d2)).astype('int64')
    x_d2_mask = numpy.zeros((n_samples, day2, maxlen_xd2)).astype('float32')
    char_d2 = numpy.zeros((n_samples, day2, maxlen_xd2, max_sequence_d2, max_char_len_d2)).astype('int64')
    # char_d2_mask = numpy.zeros((n_samples, day2, maxlen_xd2, max_sequence_d2)).astype('float32')
    final_mask = numpy.ones((n_samples, 1 + day1 + day2)).astype('float32')
    # l = numpy.array(labels).astype('int64')
    ##TODO for label
    l = numpy.zeros((n_samples,)).astype('int64')
    for index, (i, j, k, ll) in enumerate(zip(sequence, sequence_d1, sequence_d2, labels)):  # batch size
        l[index] = ll
        for idx, ss in enumerate(i):  # time step
            # x[idx, index, :sequence_length[idx]] = ss
            if len(ss) < max_sequence:
                x[index, idx, :len(ss)] = ss
            else:
                x[index, idx, :max_sequence] = ss[:max_sequence]
            x_mask[index, idx] = 1.
            for char in range(len(ss)):
                char_d0[index, idx, char, :l_seqs_d0_char[index][idx][char]] = seqs_d0_char[index][idx][char]
        for jj, day in enumerate(j):
            for idx, ss in enumerate(day):
                if len(ss) < max_sequence_d1:
                    x_d1[index, jj, idx, :len(ss)] = ss
                else:
                    x_d1[index, jj, idx, :max_sequence_d1] = ss[:max_sequence_d1]
                x_d1_mask[index, jj, idx] = 1.
                for char in range(len(ss)):
                    char_d1[index, jj, idx, char, :l_seqs_d1_char[index][jj][idx][char]] = seqs_d1_char[index][jj][idx][
                        char]
        for jj, day in enumerate(k):
            for idx, ss in enumerate(day):
                if len(ss) < max_sequence_d2:
                    x_d2[index, jj, idx, :len(ss)] = ss
                else:
                    x_d2[index, jj, idx, :max_sequence_d2] = ss[:max_sequence_d2]
                x_d2_mask[index, jj, idx] = 1.
                for char in range(len(ss)):
                    char_d2[index, jj, idx, char, :l_seqs_d2_char[index][jj][idx][char]] = seqs_d2_char[index][jj][idx][
                        char]
    '''
    haha = numpy.absolute(numpy.sign(x))
    hehe = numpy.absolute(numpy.sign(x_d1))
    jiji = numpy.absolute(numpy.sign(x_d2))
    '''
    '''
    haha = numpy.absolute(numpy.sign(char_d0))
    hehe = numpy.absolute(numpy.sign(char_d1))
    jiji = numpy.absolute(numpy.sign(char_d2))
    '''
    return x, x_mask, x_d1, x_d1_mask, x_d2, x_d2_mask, l, final_mask, char_d0, char_d1, char_d2


def days(emb, char_emb, sequence_mask, news_mask, keep_prob, is_training, options):
    # char_emb batch,day,news, sequence, char, embedding, 32*3*40*13*15*100
    # emb batch,day,news, sequence,embedding, 32*3*40*13*100
    # sequence_mask batch, day, news,sequence 32*3*40*13
    # news_mask batch, day, news, 32*3*40
    batch = tf.shape(emb)[0]
    day = tf.shape(emb)[1]
    new_s = tf.shape(emb)[2]
    word = tf.shape(emb)[3]
    char = tf.shape(char_emb)[4]
    word_level_inputs = tf.reshape(emb, [batch * day * new_s, word, options['dim_word']])
    word_level_mask = tf.reshape(sequence_mask, [batch * day * new_s, word])
    news_level_mask = tf.reshape(news_mask, [batch * day, new_s])
    char_level_inputs = tf.reshape(char_emb, [batch * day * new_s * word, char, options['dim_char_emb']])
    char_level_out = char_cnn(char_level_inputs, options, name='char_cnn')
    char_level_out = tf.reshape(char_level_out, [batch * day * new_s, word, 3 * options['CNN_filter']])
    word_level_inputs = tf.concat([word_level_inputs, char_level_out], -1)
    ##TODO word level LSTM

    word_encoder_out = bilstm_filter(word_level_inputs, word_level_mask, keep_prob,
                                     prefix='sequence_encode', dim=options['dim'],
                                     is_training=is_training)  # output shape: batch*day*news,sequence,2*lstm_units(32*3*40)*12*600
    word_encoder_out = tf.concat(word_encoder_out, 2) * tf.expand_dims(word_level_mask, -1)  # mask the output
    ##TODO word level attention
    word_level_output = attention_v2(word_encoder_out, word_level_mask, name='word_attention', keep=keep_prob, r=10,
                                     is_training=is_training)
    # word_level_output shape is (32*3*40)*600
    '''
    word_level_output = tf.reduce_sum(word_encoder_out * tf.expand_dims(word_level_mask, -1), 1) / tf.expand_dims(
        tf.reduce_sum(word_level_mask, 1) + 1e-8, 1)
    '''
    ##TODO average word
    # word_level_output = tf.reduce_sum(word_level_inputs * tf.expand_dims(word_level_mask, -1), 1) / tf.expand_dims(
    #    tf.reduce_sum(word_level_mask, 1) + 1e-8, 1)# word_level_output shape is (32*3*40)*100
    if options['use_dropout']:
        word_level_output = layers.dropout(word_level_output, keep_prob=keep_prob, is_training=is_training, seed=None)
    news_level_input = tf.reshape(word_level_output, [batch * day, new_s, 2 * options['dim']])  # (32*3)*40*600
    news_level_input = news_level_input * tf.expand_dims(news_level_mask, -1)  # mask before attention
    ##TODO news level attention
    news_level_output = attention_v2(news_level_input, news_level_mask, name='news_attention', keep=keep_prob, r=10,
                                     is_training=is_training)  # shape is (32*3)*600
    ##TODO average news
    # news_level_output = tf.reduce_sum(news_level_input * tf.expand_dims(news_level_mask, -1), 1) / tf.expand_dims(
    #    tf.reduce_sum(news_level_mask, 1) + 1e-8, 1)
    # shape is (32*3)*600
    day_level_output = tf.reshape(news_level_output, [batch, day, 2 * options['dim']])  # (32*3)*600

    return day_level_output


def news(emb, char_emb, sequence_mask, news_mask, keep_prob, is_training, options):
    # char_emb batch,news, sequence,char, embedding, 32*40*13*15*100
    # emb batch,news, sequence,embedding, 32*40*13*100
    # sequence_mask batch, news,sequence 32*40*13
    # news_mask batch, news, 32*40
    batch = tf.shape(emb)[0]
    new_s = tf.shape(emb)[1]
    word = tf.shape(emb)[2]
    char = tf.shape(char_emb)[3]
    word_level_inputs = tf.reshape(emb, [batch * new_s, word, options['dim_word']])
    word_level_mask = tf.reshape(sequence_mask, [batch * new_s, word])
    char_level_inputs = tf.reshape(char_emb, [batch * new_s * word, char, options['dim_char_emb']])
    char_level_out = char_cnn(char_level_inputs, options, name='char_cnn')
    char_level_out = tf.reshape(char_level_out, [batch * new_s, word, 3*options['CNN_filter']])
    word_level_inputs = tf.concat([word_level_inputs, char_level_out], -1)
    ##TODO word level LSTM

    word_encoder_out = bilstm_filter(word_level_inputs, word_level_mask, keep_prob,
                                     prefix='sequence_encode', dim=options['dim'],
                                     is_training=is_training)  # output shape: batch*news,sequence,2*lstm_units(32*40)*12*600
    word_encoder_out = tf.concat(word_encoder_out, 2) * tf.expand_dims(word_level_mask, -1)  # mask the output

    word_level_output = attention_v2(word_encoder_out, word_level_mask, name='word_attention', keep=keep_prob, r=10,
                                     is_training=is_training)
    '''
    word_level_output = tf.reduce_sum(word_encoder_out * tf.expand_dims(word_level_mask, -1), 1) / tf.expand_dims(
        tf.reduce_sum(word_level_mask, 1) + 1e-8, 1)
    '''
    # word_level_output shape is (32*40)*600

    ##TODO average word
    # word_level_output = tf.reduce_sum(word_level_inputs * tf.expand_dims(word_level_mask, -1), 1) / tf.expand_dims(
    #    tf.reduce_sum(word_level_mask, 1) + 1e-8, 1)# word_level_output shape is (32*40)*100
    if options['use_dropout']:
        word_level_output = layers.dropout(word_level_output, keep_prob=keep_prob, is_training=is_training, seed=None)
    news_level_input = tf.reshape(word_level_output, [batch, new_s, 2 * options['dim']])  # 32*40*600
    news_level_input = news_level_input * tf.expand_dims(news_mask, -1)  # mask before attention
    ##TODO news level attention
    news_level_output = attention_v2(news_level_input, news_mask, name='news_attention', keep=keep_prob, r=10,
                                     is_training=is_training)  # shape is 32*600
    ##TODO average news
    # news_level_output = tf.reduce_sum(news_level_input * tf.expand_dims(news_mask, -1), 1) / tf.expand_dims(
    #    tf.reduce_sum(news_mask, 1) + 1e-8, 1)
    # shape is 32*600
    return news_level_output


def attention_v1(input, masks, name='attention', nin=600, keep=1.0, is_training=True):
    # input is batch,time_step,hidden_state (32*40)*13*600 mask (32*40)*13
    # hidden layer is:batch,hidden_shape,attention_hidden_size (32*40)*13*1200 or (32*40)*13*600
    # attention shape after squeeze is (32*40)*13, # batch,time_step,attention_size (32*40)*13*1
    with tf.variable_scope(name_or_scope=name, reuse=tf.AUTO_REUSE):
        hidden = tf.layers.dense(input, nin / 2, activation=tf.nn.tanh, use_bias=True,
                                 kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                              dtype=tf.float32),
                                 name='hidden', reuse=tf.AUTO_REUSE)
        # hidden = layers.dropout(hidden, keep_prob=keep, is_training=is_training)
        # hidden = tf.layers.batch_normalization(hidden, training=is_training)
        # hidden=tf.nn.tanh(hidden)
        attention = tf.layers.dense(hidden, 1, activation=None, use_bias=False,
                                    kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                                 dtype=tf.float32),
                                    name='out',
                                    reuse=tf.AUTO_REUSE)
        padding = tf.fill(tf.shape(attention), float('-1e8'))  # float('-inf')
        attention = tf.where(tf.equal(tf.expand_dims(masks, -1), 0.), padding,
                             attention)  # fill 0 with a small number for softmax
        attention = tf.nn.softmax(attention, 1, name='softmax') * tf.expand_dims(masks,
                                                                                 -1)  # 32*40*r #mask the attention here is not really neccesary,
        results = tf.reduce_sum(input * attention, axis=1)  # 32*600
        # outputs = tf.squeeze(tf.matmul(tf.transpose(attention, [0, 2, 1]), input))  # transpose to batch,hidden,time_step
    return results


def attention_v2(input, mask, name='attention', nin=600, keep=1.0, r=10, is_training=True):
    # input is batch,time_step,hidden_state (32*40)*13*600 mask (32*40)*13
    # hidden layer is:batch,hidden_shape,attention_hidden_size (32*40)*13*1200 or (32*40)*13*600
    # attention shape after squeeze is (32*40)*13, # batch,time_step,attention_size (32*40)*13*1
    with tf.variable_scope(name_or_scope=name, reuse=tf.AUTO_REUSE):
        masks = tf.stack([mask] * r, -1)  # copy r time for filling (32*40)*13*r
        iden = tf.eye(r, batch_shape=[tf.shape(input)[0]])  # an identity matrix (32*40)*13*13
        hidden = tf.layers.dense(input, nin / 2, activation=tf.nn.tanh, use_bias=False,
                                 kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                              dtype=tf.float32),
                                 name='hidden', reuse=tf.AUTO_REUSE)
        # hidden = layers.dropout(hidden, keep_prob=keep, is_training=is_training)
        # hidden = tf.layers.batch_normalization(hidden, training=is_training)
        # hidden=tf.nn.tanh(hidden)
        attention = tf.layers.dense(hidden, r, activation=None, use_bias=False,
                                    kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                                 dtype=tf.float32),
                                    name='out',
                                    reuse=tf.AUTO_REUSE)  # attention shape is 32*40*r
        padding = tf.fill(tf.shape(attention), float('-1e8'))  # float('-inf')
        attention = tf.where(tf.equal(masks, 0.), padding, attention)  # fill 0 with a small number for softmax
        attention = tf.nn.softmax(attention, 1,
                                  name='softmax') * masks  # (32*40)*13*r #mask the attention here is not really neccesary,
        penalty = tf.norm((tf.matmul(tf.transpose(attention, [0, 2, 1]), attention) - iden), ord='fro',
                          axis=(-2, -1))  # the Frobenius norm penalty 32 dimension
        # attention = attention + beta * tf.expand_dims(tf.expand_dims(penalty, -1), -1)  # expand twice
        # outputs = tf.reduce_sum(input * attention, axis=1)#(32*40)*600
        outputs = tf.matmul(tf.transpose(attention, [0, 2, 1]), input)  # transpose to batch,hidden,time_step
        ##TODO average sentence attention
        # results = tf.reduce_mean(outputs, 1)  # average sentence attention
        ##TODO attention over attention

        over_hidden = tf.layers.dense(outputs, nin, activation=tf.nn.tanh, use_bias=False,
                                      kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                                   dtype=tf.float32),
                                      name='over_attention_hidden', reuse=tf.AUTO_REUSE)
        over_attention = tf.layers.dense(over_hidden, 1, activation=None, use_bias=False,
                                         kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                                      dtype=tf.float32),
                                         name='over_attention_out',
                                         reuse=tf.AUTO_REUSE)
        over_attention = tf.nn.softmax(over_attention, 1, name='over_attention_softmax')
        results = tf.reduce_sum(outputs * over_attention, axis=1)  # 32*600

        '''
        outputs = tf.reshape(outputs, [tf.shape(outputs)[0], -1])
        ##TODO becarful changed some thing
        if name == 'sentence_attention':
            outputs.set_shape([None, nin * (r ** 2)])
        else:
            outputs.set_shape([None, nin * r])
        '''
    return results  # result shape is batch, hidden_unit (32*40)*600


def char_cnn(input, options, name='char_cnn'):
    with tf.variable_scope(name_or_scope=name, reuse=tf.AUTO_REUSE):
        conv1 = tf.layers.conv1d(input, filters=options['CNN_filter'],
                                 kernel_size=1, padding='same', strides=1,
                                 activation=tf.nn.relu,
                                 kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                              dtype=tf.float32), name='conv1')
        conv2 = tf.layers.conv1d(input, filters=options['CNN_filter'],
                                 kernel_size=3, padding='same', strides=1,
                                 activation=tf.nn.relu,
                                 kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                              dtype=tf.float32), name='conv2')
        conv3 = tf.layers.conv1d(input, filters=options['CNN_filter'],
                                 kernel_size=5, padding='same', strides=1,
                                 activation=tf.nn.relu,
                                 kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                              dtype=tf.float32), name='conv3')
        concat = tf.concat([conv1, conv2, conv3], -1)
        gmp = tf.reduce_max(concat, reduction_indices=1, name='gmp')  ##global max pooling

    return gmp


def lstm_filter(input, mask, keep_prob, prefix='lstm', dim=300, is_training=True):
    with tf.variable_scope(name_or_scope=prefix, reuse=tf.AUTO_REUSE):
        sequence = tf.cast(tf.reduce_sum(mask, 1), tf.int32)
        lstm_fw_cell = rnn.LSTMCell(dim, forget_bias=0.0, initializer=tf.orthogonal_initializer(), state_is_tuple=True)
        keep_rate = tf.cond(is_training is not False and keep_prob < 1, lambda: 0.8, lambda: 1.0)
        cell_dp_fw = rnn.DropoutWrapper(cell=lstm_fw_cell, output_keep_prob=keep_rate)
        outputs, _ = tf.nn.dynamic_rnn(cell_dp_fw, input, sequence_length=sequence, swap_memory=False,
                                       dtype=tf.float32)
    return outputs


def bilstm_filter(input, mask, keep_prob, prefix='lstm', dim=300, is_training=True):
    with tf.variable_scope(name_or_scope=prefix, reuse=tf.AUTO_REUSE):
        sequence = tf.cast(tf.reduce_sum(mask, 1), tf.int32)
        lstm_fw_cell = rnn.LSTMBlockCell(dim,
                                         forget_bias=1.0)  # initializer=tf.orthogonal_initializer(), state_is_tuple=True
        # back directions
        lstm_bw_cell = rnn.LSTMBlockCell(dim, forget_bias=1.0)
        keep_rate = tf.cond(is_training is not False and keep_prob < 1, lambda: 0.8, lambda: 1.0)
        cell_dp_fw = rnn.DropoutWrapper(cell=lstm_fw_cell, output_keep_prob=keep_rate)
        cell_dp_bw = rnn.DropoutWrapper(cell=lstm_bw_cell, output_keep_prob=keep_rate)
        outputs, _ = tf.nn.bidirectional_dynamic_rnn(cell_dp_fw, cell_dp_bw, input, sequence_length=sequence,
                                                     swap_memory=False,
                                                     dtype=tf.float32)  # batch major
    return outputs


def init_params(options, worddicts):
    params = OrderedDict()
    # embedding
    params['Wemb'] = norm_weight(options['n_words'], options['dim_word'])
    ##TODO Charemb init
    params['Charemb'] = norm_weight(options['l_alphabet'] + 1, options['dim_char_emb'])
    # read embedding from GloVe
    if options['embedding']:
        with open(options['embedding'], 'r') as f:
            for line in f:
                tmp = line.split()
                word = tmp[0]
                vector = tmp[1:]
                if word in worddicts and worddicts[word] < options['n_words']:
                    try:
                        params['Wemb'][worddicts[word], :] = vector
                        # encoder: bidirectional RNN
                    except ValueError as e:
                        print(str(e))
    return params


def word_embedding(options, params):
    embeddings = tf.get_variable("embeddings", shape=[options['n_words'], options['dim_word']],
                                 initializer=tf.constant_initializer(numpy.array(
                                     params['Wemb'])))  # tf.constant_initializer(numpy.array(params['Wemb']))
    return embeddings


def chara_embedding(options, params
                    ):
    embeddings = tf.get_variable("char_embeddings", shape=[options['l_alphabet'] + 1, options['dim_char_emb']],
                                 initializer=tf.constant_initializer(numpy.array(
                                     params['Charemb'])))  # tf.constant_initializer(numpy.array(params['Wemb']))
    return embeddings


def build_model(embedding, character_embedding, options):
    """ Builds the entire computational graph used for training
    """
    # description string: #words x #samples
    with tf.device('/gpu:1'):
        with tf.variable_scope('input'):
            x = tf.placeholder(tf.int64, shape=[None, None, None],
                               name='x')  # 3D vector batch,news and sequence(before embedding)40*32*13
            x_mask = tf.placeholder(tf.float32, shape=[None, None], name='x_mask')  # mask batch,news
            y = tf.placeholder(tf.int64, shape=[None], name='y')
            x_d1 = tf.placeholder(tf.int64, shape=[None, None, None, None], name='x_d1')
            x_d1_mask = tf.placeholder(tf.float32, shape=[None, None, None], name='x_d1_mask')
            x_d2 = tf.placeholder(tf.int64, shape=[None, None, None, None], name='x_d2')
            x_d2_mask = tf.placeholder(tf.float32, shape=[None, None, None], name='x_d2_mask')
            final_mask = tf.placeholder(tf.float32, shape=[None, None], name='final_mask')
            tech = tf.placeholder(tf.float32, shape=[None, None, 7], name='technical')  # shape is batch time unit
            char_x = tf.placeholder(tf.int64, shape=[None, None, None, None],
                                    name='char_x')  # 4Dvector batch,news and sequence,char(before embedding)40*32*13*15
            char_x_d1 = tf.placeholder(tf.int64, shape=[None, None, None, None, None], name='char_x_d1')
            char_x_d2 = tf.placeholder(tf.int64, shape=[None, None, None, None, None], name='char_x_d2')
            # final_mask shape is day*n_samples
            ##TODO important    
            keep_prob = tf.placeholder(tf.float32, [], name='keep_prob')
            is_training = tf.placeholder(tf.bool, name='is_training')
            ##TODO important
            sequence_mask = tf.cast(tf.abs(tf.sign(x)), tf.float32)  # 3D
            sequence_d1_mask = tf.cast(tf.abs(tf.sign(x_d1)), tf.float32)  # 4D
            sequence_d2_mask = tf.cast(tf.abs(tf.sign(x_d2)), tf.float32)  # 4D
            char_mask = tf.cast(tf.abs(tf.sign(char_x)), tf.float32)  # 4D
            char_d1_mask = tf.cast(tf.abs(tf.sign(char_x_d1)), tf.float32)  # 5D
            char_d2_mask = tf.cast(tf.abs(tf.sign(char_x_d2)), tf.float32)  # 5D
            # n_timesteps = tf.shape(x)[0]  # time steps
            # n_samples = tf.shape(x)[1]  # n samples
            # # word embedding
            ##TODO word embedding
            emb = tf.nn.embedding_lookup(embedding, x)
            emb_d1 = tf.nn.embedding_lookup(embedding, x_d1)
            emb_d2 = tf.nn.embedding_lookup(embedding, x_d2)
            char_emb_x = tf.nn.embedding_lookup(character_embedding, char_x)  # 5D
            char_emb_d1 = tf.nn.embedding_lookup(character_embedding, char_x_d1)  # 6D
            char_emb_d2 = tf.nn.embedding_lookup(character_embedding, char_x_d2)  # 6D
            ##TODO mask the character embedding
            char_emb_x = tf.multiply(char_emb_x, tf.expand_dims(char_mask, -1))
            char_emb_d1 = tf.multiply(char_emb_d1, tf.expand_dims(char_d1_mask, -1))
            char_emb_d2 = tf.multiply(char_emb_d2, tf.expand_dims(char_d2_mask, -1))
            '''if options['use_dropout']:
            emb = layers.dropout(emb, keep_prob=keep_prob, is_training=is_training)
            '''
    with tf.device('/gpu:1'):
        # fed into the input of BILSTM from the official document
        ##TODO word level LSTM
        with tf.name_scope('news'):
            att = news(emb, char_emb_x, sequence_mask, x_mask, keep_prob, is_training, options)
        ##TODO att shape 32*600 att_day1 32*3*600 att_day2 32*4*600
        with tf.name_scope('day1'):
            att_day1 = days(emb_d1, char_emb_d1, sequence_d1_mask, x_d1_mask, keep_prob, is_training, options)
        # TODO bilstm layers
        # Change the time step and batch
    with tf.device('/gpu:1'):
        with tf.name_scope('day2'):
            att_day2 = days(emb_d2, char_emb_d2, sequence_d2_mask, x_d2_mask, keep_prob, is_training, options)
        with tf.name_scope('final'):
            final = tf.concat([att_day2, att_day1, tf.expand_dims(att, 1)], 1)
            '''if options['use_dropout']:
                final = layers.dropout(final, keep_prob=keep_prob, is_training=is_training)
            '''
            # final shape is 8*32*600
            if options['last_layer'] == 'LSTM':
                final = bilstm_filter(final, final_mask, keep_prob, prefix='day_lstm', dim=100,
                                      is_training=is_training)  # output shape: batch,time_step,2*lstm_unit(concate) 32*7*600
                # tech_ind = lstm_filter(tech, tf.ones(shape=[tf.shape(tech)[0],tf.shape(tech)[1]]), keep_prob, prefix='tech_lstm', dim=50,
                #                    is_training=is_training)
                ##TODO day level attention
                att_final = attention_v2(tf.concat(final, 2), final_mask, name='day_attention', keep=keep_prob, r=4,
                                         is_training=is_training)  # already masked after attention
                ##TODO take day lstm average
                # att_final = tf.reduce_mean(tf.concat(final,2),1)
                # tech_att = tf.reduce_mean(tf.concat(tech_ind,2),1)
                ##TODO take the lasts
                # tech_att=tech_ind[:,-1,:]
                # att_final = tf.concat([att_final,tech_att],axis=1)
                logit = tf.layers.dense(att_final, 100, activation=tf.nn.tanh, use_bias=True,
                                        kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                                     dtype=tf.float32),
                                        name='ff', reuse=tf.AUTO_REUSE)
                # logit = tf.layers.batch_normalization(logit, training=is_training)
                # logit=tf.nn.tanh(logit)

                '''
                # logit1 = tf.reduce_sum(tf.concat(final,2) * tf.expand_dims(final_mask,-1),0) / tf.expand_dims(tf.reduce_sum(final_mask,0),1)
                # logit2 = tf.reduce_max(ctx3 * tf.expand_dims(x1_mask,2),0)
                '''
            if options['last_layer'] == 'CNN':
                att_ctx = tf.concat([att_day1, tf.expand_dims(att, 1)], 1)
                xavier = layers.xavier_initializer(uniform=True, seed=None, dtype=tf.float32)
                conv1 = tf.layers.conv1d(att_ctx, filters=options['CNN_filter'],
                                         kernel_size=options['CNN_kernel'], padding='same', strides=1,
                                         activation=tf.nn.relu, kernel_initializer=xavier, name='conv1')
                conv2 = tf.layers.conv1d(final, filters=options['CNN_filter'],
                                         kernel_size=options['CNN_kernel'], padding='same',
                                         strides=1, activation=tf.nn.relu,
                                         kernel_initializer=xavier,
                                         name='conv2')

                pool1 = tf.layers.max_pooling1d(conv1, pool_size=2, strides=2, padding='same',
                                                data_format='channels_last', name='pool1')
                pool2 = tf.layers.max_pooling1d(conv2, pool_size=2, strides=2, padding='same',
                                                data_format='channels_last', name='pool2')
                d1size = math.ceil(options['delay1'] / 2) * options['CNN_filter']
                d2size = math.ceil(options['delay2'] / 2) * options['CNN_filter']
                pool1_flat = tf.reshape(pool1, [-1, d1size])
                pool2_flat = tf.reshape(pool2, [-1, d2size])
                cnn_final = tf.concat([att, pool1_flat, pool2_flat], -1)
                logit = tf.layers.dense(cnn_final, 300, activation=tf.nn.tanh, use_bias=True,
                                        kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                                     dtype=tf.float32),
                                        name='ff', reuse=tf.AUTO_REUSE)
                # logit = tf.layers.batch_normalization(logit, training=is_training)
                # logit=tf.nn.tanh(logit)

            if options['use_dropout']:
                logit = layers.dropout(logit, keep_prob=keep_prob, is_training=is_training, seed=None)
            pred = tf.layers.dense(logit, 2, activation=None, use_bias=True,
                                   kernel_initializer=layers.xavier_initializer(uniform=True, seed=None,
                                                                                dtype=tf.float32),
                                   name='fout', reuse=tf.AUTO_REUSE)
            logger.info('Building f_cost...')
            # todo not same
            labels = tf.one_hot(y, depth=2, axis=1)
            # labels = y
            preds = tf.nn.softmax(pred, 1, name='softmax')
            # preds = tf.nn.sigmoid(pred)
            # pred=tf.reshape(pred,[-1])
            cost = tf.nn.softmax_cross_entropy_with_logits_v2(logits=pred, labels=labels)
            # cost = tf.reduce_sum(tf.nn.sigmoid_cross_entropy_with_logits(labels=labels,logits=pred),1)
            # cost = -tf.reduce_sum((tf.cast(labels, tf.float32) * tf.log(preds + 1e-8)),axis=1)
            # cost = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=pred, labels=y)
        logger.info('Done')
        '''
        logit1 = tf.reduce_sum(ctx1 * tf.expand_dims(x_mask, 2), 0) / tf.expand_dims(tf.reduce_sum(x_mask, 0), 1)
        logit2 = tf.reduce_max(ctx1 * tf.expand_dims(x_mask, 2), 0)
        logit = tf.concat([logit1, logit2], 1)
        '''

        with tf.variable_scope('logging'):
            tf.summary.scalar('current_cost', tf.reduce_mean(cost))
            tf.summary.histogram('predicted_value', preds)
            summary = tf.summary.merge_all()

    return is_training, cost, x, x_mask, y, preds, summary


def predict_pro_acc(sess, cost, prepare_data, model_options, iterator, maxlen, correct_pred, pred, summary, eidx,
                    is_training, train_op, plot=None, writer=None, validate=False):
    # fo = open(_s(prefix,'pre.txt'), "w")
    num = 0
    valid_acc = 0
    total_cost = 0
    loss = 0
    result = 0
    final_result = []
    # sess.add_tensor_filter("val_test_spot")
    for x_sent, x_d1_sent, x_d2_sent, y_sent, y_tech, max_word_len in iterator:
        num += len(x_sent)
        data_x, data_x_mask, data_x_d1, data_x_d1_mask, data_x_d2, data_x_d2_mask, data_y, final_mask, char_x, char_x_d1, char_x_d2 = prepare_data(
            x_sent,
            x_d1_sent,
            x_d2_sent,
            y_sent,
            max_word_len,
            model_options,
            maxlen=maxlen)

        loss, result, preds = sess.run([cost, correct_pred, pred],
                                       feed_dict={'input/x:0': data_x, 'input/x_mask:0': data_x_mask,
                                                  'input/y:0': data_y, 'input/x_d1:0': data_x_d1,
                                                  'input/x_d1_mask:0': data_x_d1_mask,
                                                  'input/x_d2:0': data_x_d2, 'input/x_d2_mask:0': data_x_d2_mask,
                                                  'input/final_mask:0': final_mask,
                                                  'input/technical:0': y_tech,
                                                  'input/char_x:0': char_x,
                                                  'input/char_x_d1:0': char_x_d1,
                                                  'input/char_x_d2:0': char_x_d2,
                                                  'input/keep_prob:0': 1.0,
                                                  'input/is_training:0': is_training})
        valid_acc += result.sum()
        total_cost += loss.sum()
        if plot is not None:
            if validate is True:
                plot['validate'].append(loss.sum() / len(x_sent))
            else:
                plot['testing'].append(loss.sum() / len(x_sent))
        final_result.extend(result.tolist())
    final_acc = 1.0 * valid_acc / num
    final_loss = 1.0 * total_cost / num
    # if writer is not None:
    #    writer.add_summary(test_summary, eidx)

    # print result,preds,loss,result_
    print(preds, result, num)

    return final_acc, final_loss, final_result


def train(
        dim_word=100,  # word vector dimensionality
        dim=100,  # the number of GRU units
        encoder='lstm',  # encoder model
        decoder='lstm',  # decoder model
        patience=10,  # early stopping patience
        max_epochs=5000,
        finish_after=10000000,  # finish after this many updates
        decay_c=0.,  # L2 regularization penalty
        clip_c=-1.,  # gradient clipping threshold
        lrate=0.0004,  # learning rate
        n_words=100000,  # vocabulary size
        n_words_lemma=100000,
        maxlen=100,  # maximum length of the description
        optimizer='adam',
        batch_size=32,
        valid_batch_size=32,
        save_model='../../models/',
        saveto='model.npz',
        dispFreq=100,
        validFreq=1000,
        saveFreq=1000,  # save the parameters after every saveFreq updates
        use_dropout=False,
        reload_=False,
        verbose=False,  # print verbose information for debug but slow speed
        delay1=3,
        delay2=7,
        delay_tech=5,
        types='title',
        cut_word=False,
        cut_news=False,
        last_layer="LSTM",
        CNN_filter=64,
        CNN_kernel=3,
        keep_prob=0.8,
        datasets=[],
        valid_datasets=[],
        test_datasets=[],
        tech_data=[],
        dictionary=[],
        kb_dicts=[],
        embedding='',  # pretrain embedding file, such as word2vec, GLOVE
        dim_kb=5,
        RUN_NAME="histogram_visualization",
        wait_N=10
):
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s: %(name)s: %(levelname)s: %(message)s",
                        filename='./log_result.txt')
    # Model options
    model_options = locals().copy()

    model_options[
        'alphabet'] = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-,;.!?:'\"/\\|_@#$%^&*~`+-=<>()[]{}"
    model_options['l_alphabet'] = len(model_options['alphabet'])
    model_options['dim_char_emb'] = 15
    model_options['char_nout'] = 100
    model_options['char_k_rows'] = [1, 3, 5]
    model_options['char_k_cols'] = model_options['dim_char_emb']

    # tf.reset_default_graph()
    # tf.set_random_seed(2345)
    with open(dictionary, 'rb') as f:
        worddicts = pkl.load(f)
    worddicts_r = dict()
    for kk, vv in worddicts.items():
        worddicts_r[vv] = kk

    logger.info("Loading knowledge base ...")

    # reload options
    if reload_ and os.path.exists(saveto):
        logger.info("Reload options")
        with open('%s.pkl' % saveto, 'rb') as f:
            model_options = pkl.load(f)

    logger.debug(pprint.pformat(model_options))

    logger.info("Loading data")
    train = TextIterator(datasets[0], datasets[1], tech_data,
                         dict=dictionary,
                         delay1=delay1,
                         delay2=delay2,
                         delay_tech=delay_tech,
                         types=types,
                         n_words=n_words,
                         batch_size=batch_size,
                         cut_word=cut_word,
                         cut_news=cut_news,
                         shuffle=True, shuffle_sentence=False)
    train_valid = TextIterator(datasets[0], datasets[1], tech_data,
                               dict=dictionary,
                               delay1=delay1,
                               delay2=delay2,
                               delay_tech=delay_tech,
                               types=types,
                               n_words=n_words,
                               batch_size=valid_batch_size,
                               cut_word=cut_word,
                               cut_news=cut_news,
                               shuffle=False, shuffle_sentence=False)
    valid = TextIterator(valid_datasets[0], valid_datasets[1], tech_data,
                         dict=dictionary,
                         delay1=delay1,
                         delay2=delay2,
                         delay_tech=delay_tech,
                         types=types,
                         n_words=n_words,
                         batch_size=valid_batch_size,
                         cut_word=cut_word,
                         cut_news=cut_news,
                         shuffle=False, shuffle_sentence=False)
    test = TextIterator(test_datasets[0], test_datasets[1], tech_data,
                        dict=dictionary,
                        delay1=delay1,
                        delay2=delay2,
                        delay_tech=delay_tech,
                        types=types,
                        n_words=n_words,
                        batch_size=valid_batch_size,
                        cut_word=cut_word,
                        cut_news=cut_news,
                        shuffle=False, shuffle_sentence=False)

    # Initialize (or reload) the parameters using 'model_options'
    # then build the tensorflow graph
    logger.info("init_word_embedding and char_embedding")
    params = init_params(model_options, worddicts)
    embedding = word_embedding(model_options, params)
    character_embedding = chara_embedding(model_options, params)
    is_training, cost, x, x_mask, y, pred, summary = build_model(embedding, character_embedding, model_options)
    with tf.variable_scope('train'):
        lr = tf.Variable(0.0, trainable=False)

        def assign_lr(session, lr_value):
            session.run(tf.assign(lr, lr_value))

        logger.info('Building optimizers...')
        # optimizer = tf.train.AdamOptimizer(learning_rate=lr)
        optimizer = tf.train.AdadeltaOptimizer(learning_rate=lr, rho=0.95)
        logger.info('Done')
        # print all variables
        tvars = tf.trainable_variables()
        for var in tvars:
            print(var.name, var.shape)
        lossL = tf.add_n([tf.nn.l2_loss(v) for v in tvars if ('embeddings' not in v.name and 'bias' not in v.name)])  #
        lossL2 = lossL * 0.0005
        print("don't do L2 variables:")
        print([v.name for v in tvars if ('embeddings' in v.name or 'bias' in v.name)])
        print("\n do L2 variables:")
        print([v.name for v in tvars if ('embeddings' not in v.name and 'bias' not in v.name)])
        cost = cost + lossL2
        grads, _ = tf.clip_by_global_norm(tf.gradients(cost, tvars), model_options['clip_c'])
        extra_update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(extra_update_ops):
            train_op = optimizer.apply_gradients(zip(grads, tvars))
        # train_op = optimizer.minimize(cost)
        op_loss = tf.reduce_mean(cost)
        op_L2 = tf.reduce_mean(lossL)
        logger.info("correct_pred")
        correct_pred = tf.equal(tf.argmax(input=pred, axis=1), y)  # make prediction
        logger.info("Done")

        temp_accuracy = tf.cast(correct_pred, tf.float32)  # change to float32

    logger.info("init variables")
    init = tf.global_variables_initializer()
    logger.info("Done")
    # saver
    saver = tf.train.Saver(max_to_keep=15)

    config = tf.ConfigProto()
    # config.gpu_options.per_process_gpu_memory_fraction = 0.4
    config.gpu_options.allow_growth = True
    # gpu_options = tf.GPUOptions(allow_growth=True)
    # sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))
    with tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=False)) as sess:
        # sess = tf_debug.LocalCLIDebugWrapperSession(sess)
        training_writer = tf.summary.FileWriter("./logs/{}/training".format(RUN_NAME), sess.graph)
        validate_writer = tf.summary.FileWriter("./logs/{}/validate".format(RUN_NAME), sess.graph)
        testing_writer = tf.summary.FileWriter("./logs/{}/testing".format(RUN_NAME), sess.graph)
        sess.run(init)
        history_errs = []
        history_valid_result = []
        history_test_result = []
        # reload history
        if reload_ and os.path.exists(saveto):
            logger.info("Reload history error")
            history_errs = list(numpy.load(saveto)['history_errs'])

        bad_counter = 0

        if validFreq == -1:
            validFreq = len(train[0]) / batch_size
        if saveFreq == -1:
            saveFreq = len(train[0]) / batch_size

        loss_plot = defaultdict(list)
        uidx = 0
        estop = False
        valid_acc_record = []
        test_acc_record = []
        best_num = -1
        best_epoch_num = 0
        lr_change_list = []
        fine_tune_flag = 0
        wait_counter = 0
        wait_N = model_options['wait_N']
        learning_rate = model_options['lrate']
        assign_lr(sess, learning_rate)
        for eidx in range(max_epochs):
            n_samples = 0
            training_cost = 0
            training_acc = 0
            for x, x_d1, x_d2, y, y_tech, max_word_len in train:
                n_samples += len(x)
                uidx += 1
                keep_prob = model_options['keep_prob']
                is_training = True
                data_x, data_x_mask, data_x_d1, data_x_d1_mask, data_x_d2, data_x_d2_mask, data_y, final_mask, char_x, char_x_d1, char_x_d2 = prepare_data(
                    x,
                    x_d1,
                    x_d2,
                    y,
                    max_word_len,
                    model_options,
                    worddicts_r,
                    maxlen=maxlen)
                print(data_x.shape, data_x_d1.shape, data_x_d2.shape, char_x.shape, char_x_d1.shape, char_x_d2.shape,
                      data_y.shape)
                assert data_y.shape[0] == data_x.shape[0], 'Size does not match'
                if x is None:
                    logger.debug('Minibatch with zero sample under length {0}'.format(maxlen))
                    uidx -= 1
                    continue
                ud_start = time.time()
                _, loss, loss_no_mean, temp_acc, l2_check = sess.run([train_op, op_loss, cost, temp_accuracy, op_L2],
                                                                     feed_dict={'input/x:0': data_x,
                                                                                'input/x_mask:0': data_x_mask,
                                                                                'input/y:0': data_y,
                                                                                'input/x_d1:0': data_x_d1,
                                                                                'input/x_d1_mask:0': data_x_d1_mask,
                                                                                'input/x_d2:0': data_x_d2,
                                                                                'input/x_d2_mask:0': data_x_d2_mask,
                                                                                'input/final_mask:0': final_mask,
                                                                                'input/technical:0': y_tech,
                                                                                'input/char_x:0': char_x,
                                                                                'input/char_x_d1:0': char_x_d1,
                                                                                'input/char_x_d2:0': char_x_d2,
                                                                                'input/keep_prob:0': keep_prob,
                                                                                'input/is_training:0': is_training})
                ud = time.time() - ud_start
                training_cost += loss_no_mean.sum()
                training_acc += temp_acc.sum()
                loss_plot['training'].append(loss)
                '''train_summary = sess.run(summary, feed_dict={'input/x:0': data_x, 'input/x_mask:0': data_x_mask,
                                                              'input/y:0': data_y,'input/keep_prob:0':keep_prob,'input/is_training:0':is_training})
                training_writer.add_summary(train_summary, eidx)'''
                if numpy.mod(uidx, dispFreq) == 0:
                    logger.debug('Epoch {0} Update {1} Cost {2} L2 {3} TIME {4}'.format(eidx, uidx, loss, l2_check, ud))

                # validate model on validation set and early stop if necessary
                if numpy.mod(uidx, validFreq) == 0:
                    is_training = False

                    valid_acc, valid_loss, valid_final_result = predict_pro_acc(sess, cost, prepare_data, model_options,
                                                                                valid, maxlen,
                                                                                correct_pred, pred, summary, eidx,
                                                                                is_training, train_op, loss_plot,
                                                                                validate_writer, validate=True)
                    test_acc, test_loss, test_final_result = predict_pro_acc(sess, cost, prepare_data, model_options,
                                                                             test, maxlen,
                                                                             correct_pred, pred, summary, eidx,
                                                                             is_training, train_op, loss_plot,
                                                                             testing_writer)
                    # valid_err = 1.0 - valid_acc
                    valid_err = valid_loss
                    history_errs.append(valid_err)
                    history_valid_result.append(valid_final_result)
                    history_test_result.append(test_final_result)
                    loss_plot['validate_ep'].append(valid_loss)
                    loss_plot['testing_ep'].append(test_loss)
                    logger.debug('Epoch  {0}'.format(eidx))
                    logger.debug('Valid cost  {0}'.format(valid_loss))
                    logger.debug('Valid accuracy  {0}'.format(valid_acc))
                    logger.debug('Test cost  {0}'.format(test_loss))
                    logger.debug('Test accuracy  {0}'.format(test_acc))
                    logger.debug('learning_rate:  {0}'.format(learning_rate))

                    valid_acc_record.append(valid_acc)
                    test_acc_record.append(test_acc)
                    if uidx == 0 or valid_err <= numpy.array(history_errs).min():
                        best_num = best_num + 1
                        best_epoch_num = eidx
                        wait_counter = 0
                        logger.info("Saving...")
                        saver.save(sess, _s(_s(_s(save_model, "epoch"), str(best_num)), "model.ckpt"))
                        logger.info(_s(_s(_s(save_model, "epoch"), str(best_num)), "model.ckpt"))
                        numpy.savez(saveto, history_errs=history_errs, **params)
                        pkl.dump(model_options, open('{}.pkl'.format(saveto), 'wb'))
                        logger.info("Done")

                    if valid_err > numpy.array(history_errs).min():
                        wait_counter += 1
                    # wait_counter +=1 if valid_err>numpy.array(history_errs).min() else 0
                    if wait_counter >= wait_N:
                        logger.info("wait_counter max, need to half the lr")
                        # print 'wait_counter max, need to half the lr'
                        bad_counter += 1
                        wait_counter = 0
                        logger.debug('bad_counter:  {0}'.format(bad_counter))
                        # TODO change the learining rate
                        # learning_rate = learning_rate * 0.9
                        # learning_rate = learning_rate
                        # assign_lr(sess, learning_rate)
                        lr_change_list.append(eidx)
                        logger.debug('lrate change to:   {0}'.format(learning_rate))
                        # print 'lrate change to: ' + str(lrate)

                    if bad_counter > patience and fine_tune_flag == 0:
                        logger.debug('ATTENTION! INTO FINE TUNING STAGE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                        optimizer = tf.train.MomentumOptimizer(learning_rate=0.000001, momentum=0.6)
                        fine_tune_flag = 1
                        bad_counter = 0
                    if bad_counter > patience and fine_tune_flag == 1:
                        logger.info("Early Stop!")
                        estop = True
                        break

                    if numpy.isnan(valid_err):
                        pdb.set_trace()

                        # finish after this many updates
                if uidx >= finish_after:
                    logger.debug('Finishing after iterations!  {0}'.format(uidx))
                    # print 'Finishing after %d iterations!' % uidx
                    estop = True
                    break
            logger.debug('Seen samples:  {0}'.format(n_samples))
            logger.debug('Training accuracy:  {0}'.format(1.0 * training_acc / n_samples))
            loss_plot['training_ep'].append(training_cost / n_samples)
            # print 'Seen %d samples' % n_samples
            logger.debug('Saved loss_plot pickle')
            with open("important_plot.pickle", 'wb') as handle:
                pkl.dump(loss_plot, handle, protocol=pkl.HIGHEST_PROTOCOL)
            if estop:
                break

    with tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=False)) as sess:
        # Restore variables from disk.
        saver.restore(sess, _s(_s(_s(save_model, "epoch"), str(best_num)), "model.ckpt"))
        keep_prob = 1
        is_training = False
        logger.info('=' * 80)
        logger.info('Final Result')
        logger.info('=' * 80)
        logger.debug('best epoch   {0}'.format(best_epoch_num))

        valid_acc, valid_cost, valid_final_result = predict_pro_acc(sess, cost, prepare_data, model_options, valid,
                                                                    maxlen, correct_pred, pred, summary, eidx, train_op,
                                                                    is_training, None)
        logger.debug('Valid cost   {0}'.format(valid_cost))
        logger.debug('Valid accuracy   {0}'.format(valid_acc))

        # print 'Valid cost', valid_cost
        # print 'Valid accuracy', valid_acc

        test_acc, test_cost, test_final_result = predict_pro_acc(sess, cost, prepare_data, model_options, test,
                                                                 maxlen, correct_pred, pred, summary, eidx, train_op,
                                                                 is_training, None)
        logger.debug('Test cost   {0}'.format(test_cost))
        logger.debug('Test accuracy   {0}'.format(test_acc))

        # print 'best epoch ', best_epoch_num
        train_acc, train_cost, _ = predict_pro_acc(sess, cost, prepare_data, model_options, train_valid,
                                                   maxlen, correct_pred, pred, summary, eidx, train_op, is_training,
                                                   None)
        logger.debug('Train cost   {0}'.format(train_cost))
        logger.debug('Train accuracy   {0}'.format(train_acc))
        valid_m = numpy.array(history_valid_result)
        test_m = numpy.array(history_test_result)
        valid_final_result = (numpy.array([valid_final_result]) == False)
        test_final_result = (numpy.array([test_final_result]) == False)
        # print(numpy.all(valid_m, axis = 0))
        # print(numpy.all(test_m, axis=0))
        print('validation: all prediction through every epoch that are the same:',
              numpy.where(numpy.all(valid_m, axis=0)))
        print('testing: all prediction through every epoch that are the same:', numpy.where(numpy.all(test_m, axis=0)))
        print('validation: final prediction that is False:', numpy.where(valid_final_result))
        print('testing: final prediction that is False:', numpy.where(test_final_result))
        if os.path.exists('history_predict.npz'):
            logger.info("Load and save to history_predict.npz")
            valid_history = numpy.load('history_predict.npz')['valid_final_result']
            test_history = numpy.load('history_predict.npz')['test_final_result']
            vv = numpy.concatenate((valid_history, valid_final_result), axis=0)
            tt = numpy.concatenate((test_history, valid_final_result), axis=0)
            print('Concate shape valid:', vv.shape)
            print('Print all validate history outputs that return False', numpy.where(numpy.all(vv, axis=0)))
            print('Concate shape test:', tt.shape)
            print('Print all test history outputs that return False', numpy.where(numpy.all(tt, axis=0)))
            numpy.savez('history_predict.npz', valid_final_result=vv, test_final_result=tt, **params)
        else:
            numpy.savez('history_predict.npz', valid_final_result=valid_final_result,
                        test_final_result=test_final_result, **params)
        # print 'Train cost', train_cost
        # print 'Train accuracy', train_acc

        # print 'Test cost   ', test_cost
        # print 'Test accuracy   ', test_acc

        return None


if __name__ == '__main__':
    pass
