
from keras.preprocessing.image import img_to_array
from keras.applications.densenet import DenseNet169, DenseNet121, preprocess_input,decode_predictions
from keras.preprocessing.image import ImageDataGenerator, load_img
from keras.models import Sequential, Model, load_model
from keras.layers import Conv2D, MaxPool2D
from keras.layers import Activation, Dropout, Flatten, Dense
from keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint, Callback
from keras import regularizers
import pandas as pd
from tqdm import tqdm
import os
import scipy as sp
import keras
import numpy as np
import tensorflow as tf
import random
from keras.optimizers import Adam
import keras.backend as K
import cv2
import matplotlib.pyplot as plt
import requests
import ssl

ssl._create_default_https_context = ssl._create_unverified_context


def preprocess_image(image1):
    image = load_img(image1, target_size=(224, 224))
    mean = 66.39297
    std = 49.230354
    # convert the image pixels to a numpy array
    image = img_to_array(image)
    float_image = image.astype('float32')
    float_image[:, :, :] = (float_image[:, :, :] - mean) / std

    # reshape data for the model
    array = np.reshape(float_image, newshape=(1, 224, 224, 3))
    return array

def build_model(n_classes):
    base_model = DenseNet169(input_shape=(224,224,3),
                             weights='imagenet',
                             include_top=False,
                             pooling='avg')

    x = base_model.output

    predictions = Dense(n_classes,activation='sigmoid')(x)
    model = Model(inputs=base_model.input, outputs=predictions)
    model.load_weights('weights/densenet_mura_rs_v3_xr_shoulder.h5')
    model.summary()
    return model

def predict(image1,n_classes=1):
    model = build_model(n_classes)
    print(type(image1))
    print(image1)
    for ilayer, layer in enumerate(model.layers):
        print("{:3.0f} {:10}".format(ilayer, layer.name))
    image=preprocess_image(image1)
    print(image.shape)
    # prepare the image for the VGG model
    # predict the probability across all output classes
    yhat = model.predict(image)

    print(yhat)
    # convert the probabilities to class labels
    #label = decode_predictions(yhat)
    # retrieve the most likely result, e.g. highest probability
    #label = label[0][0]
    #return label
    return yhat


last_conv_layer_name='conv5_block32_concat'
last_classifier_name=['avg_pool','dense_1']

def make_gradcam_heatmap(img_array, model, last_conv_layer_name, classifier_layer_names):
    # https://keras.io/examples/vision/grad_cam/
    # First, we create a model that maps the input image to the activations
    # of the last conv layer
    last_conv_layer = model.get_layer(last_conv_layer_name)
    last_conv_layer_model = keras.Model(model.inputs, last_conv_layer.output)

    # Second, we create a model that maps the activations of the last conv
    # layer to the final class predictions
    classifier_input = keras.Input(shape=last_conv_layer.output.shape[1:])
    x = classifier_input
    for layer_name in classifier_layer_names:
        x = model.get_layer(layer_name)(x)
    classifier_model = keras.Model(classifier_input, x)

    # Then, we compute the gradient of the top predicted class for our input image
    # with respect to the activations of the last conv layer
    with tf.GradientTape() as tape:
        # Compute activations of the last conv layer and make the tape watch it
        last_conv_layer_output = last_conv_layer_model(img_array)
        tape.watch(last_conv_layer_output)
        # Compute class predictions
        preds = classifier_model(last_conv_layer_output)
        top_pred_index = tf.argmax(preds[0])
        top_class_channel = preds[:, top_pred_index]

    # This is the gradient of the top predicted class with regard to
    # the output feature map of the last conv layer
    grads = tape.gradient(top_class_channel, last_conv_layer_output)

    # This is a vector where each entry is the mean intensity of the gradient
    # over a specific feature map channel
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    # We multiply each channel in the feature map array
    # by "how important this channel is" with regard to the top predicted class
    last_conv_layer_output = last_conv_layer_output.numpy()[0]
    pooled_grads = pooled_grads.numpy()
    for i in range(pooled_grads.shape[-1]):
        last_conv_layer_output[:, :, i] *= pooled_grads[i]

    # The channel-wise mean of the resulting feature map
    # is our heatmap of class activation
    heatmap = np.mean(last_conv_layer_output, axis=-1)

    # For visualization purpose, we will also normalize the heatmap between 0 & 1
    heatmap = np.maximum(heatmap, 0) / np.max(heatmap)
    print('shape of heatmap: ',heatmap.shape)
    print('heatmap content: ', heatmap)


    return heatmap


def predict_heatmap(image1,n_classes):
    prediction=predict(image1,n_classes)
    model = build_model(n_classes)
    float_image=preprocess_image(image1)
    heatmap=make_gradcam_heatmap(classifier_layer_names=last_classifier_name,last_conv_layer_name=last_conv_layer_name,img_array=float_image,model=model)
    return (prediction,heatmap,float_image)