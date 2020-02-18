import os
import numpy as np
from skimage import measure
from skimage.io import imread
from skimage.filters import threshold_otsu
from PIL import Image
import scipy.fftpack # For FFT2
import pandas as pd
import cv2
import matplotlib.pyplot as plt

FILES = os.listdir("data")
CSV_FILES = pd.read_csv("data/trainVal.csv")

def image_extraction(csv_files, channel):
    """
    the images to be extxracted are grayscale
    extract images from images/grayscale
    """
    i = 0
    raw_data = []
    labels = []
    for _, row in csv_files.iterrows():
        i = i + 1
        file = row['image_path']
        label = row['lp']
        op_filename = "images/grayscale/" + file.split(sep='/')[1] + "/" + file.split(sep='/')[2].replace(".png", ".jpg")
        print(op_filename)
        ip_filename = "data/"+ file.split(sep='/')[1] + '/' + file.split(sep='/')[2]
        print(ip_filename)
        img = cv2.imread(ip_filename, channel)
        raw_data.append(img)
        labels.append(label)
    print(i)
    return raw_data, labels

def imclearborder(imgBW, radius):
    """
    Given a black and white image, first find all of its contours
    """
    imgBWcopy = imgBW.copy()
    _, contours, _ = cv2.findContours(imgBWcopy.copy(),
                                      cv2.RETR_LIST,
                                      cv2.CHAIN_APPROX_SIMPLE)
    # Get dimensions of image
    imgRows = imgBW.shape[0]
    imgCols = imgBW.shape[1]
    # ID list of contours that touch the border
    contourList = []
    # For each contour...
    for idx in np.arange(len(contours)):
        # Get the i'th contour
        cnt = contours[idx]
        # Look at each point in the contour
        for pt in cnt:
            rowCnt = pt[0][1]
            colCnt = pt[0][0]
            # If this is within the radius of the border
            # this contour goes bye bye!
            check1 = (rowCnt >= 0 and rowCnt < radius) or (rowCnt >= imgRows-1-radius and rowCnt < imgRows)
            check2 = (colCnt >= 0 and colCnt < radius) or (colCnt >= imgCols-1-radius and colCnt < imgCols)
            if check1 or check2:
                contourList.append(idx)
                break
    for idx in contourList:
        cv2.drawContours(imgBWcopy, contours, idx, (0, 0, 0), -1)
    return imgBWcopy

def bwareaopen(imgBW, areaPixels):
    """
    Given a black and white image, first find all of its contours
    """
    imgBWcopy = imgBW.copy()
    _, contours, _ = cv2.findContours(imgBWcopy.copy(),
                                      cv2.RETR_LIST,
                                      cv2.CHAIN_APPROX_SIMPLE)
    # For each contour, determine its total occupying area
    for idx in np.arange(len(contours)):
        area = cv2.contourArea(contours[idx])
        if (area >= 0 and area <= areaPixels):
            cv2.drawContours(imgBWcopy, contours, idx, (0, 0, 0), -1)
    return imgBWcopy

def homomorphic_filter(csv_files):
    """
    to improve the area of observation in the license plate.
    """
    filtered_data = []
    labels = []
    i = 0
    for _, row in csv_files.iterrows():
        i = i + 1
        try:
            file = row['image_path']
            label = row['lp']
            filename = "data/"+ file.split(sep='/')[1] + '/' + file.split(sep='/')[2]
            print(i, filename)
            img = cv2.imread(filename, 0)
            # Number of rows and columns
            rows = img.shape[0]
            cols = img.shape[1]
            # Remove some columns from the beginning and end
            img = img[:, 59:cols-20]
            # Number of rows and columns
            rows = img.shape[0]
            cols = img.shape[1]
            # Convert image to 0 to 1, then do log(1 + I)
            imgLog = np.log1p(np.array(img, dtype="float") / 255)
            # Create Gaussian mask of sigma = 10
            M = 2*rows + 1
            N = 2*cols + 1
            sigma = 10
            (X, Y) = np.meshgrid(np.linspace(0, N-1, N), np.linspace(0, M-1, M))
            centerX = np.ceil(N/2)
            centerY = np.ceil(M/2)
            gaussianNumerator = (X - centerX)**2 + (Y - centerY)**2
            # Low pass and high pass filters
            Hlow = np.exp(-gaussianNumerator / (2*sigma*sigma))
            Hhigh = 1 - Hlow
            # Move origin of filters so that it's at the top left corner to
            # match with the input image
            HlowShift = scipy.fftpack.ifftshift(Hlow.copy())
            HhighShift = scipy.fftpack.ifftshift(Hhigh.copy())
            # Filter the image and crop
            If = scipy.fftpack.fft2(imgLog.copy(), (M, N))
            Ioutlow = scipy.real(scipy.fftpack.ifft2(If.copy() * HlowShift, (M, N)))
            Iouthigh = scipy.real(scipy.fftpack.ifft2(If.copy() * HhighShift, (M, N)))
            # Set scaling factors and add
            gamma1 = 0.3
            gamma2 = 1.5
            Iout = gamma1*Ioutlow[0:rows, 0:cols] + gamma2*Iouthigh[0:rows, 0:cols]
            # Anti-log then rescale to [0,1]
            Ihmf = np.expm1(Iout)
            Ihmf = (Ihmf - np.min(Ihmf)) / (np.max(Ihmf) - np.min(Ihmf))
            Ihmf2 = np.array(255*Ihmf, dtype="uint8")
            # Threshold the image - Anything below intensity 65 gets set to white
            Ithresh = Ihmf2 < 65
            Ithresh = 255*Ithresh.astype("uint8")
            # Clear off the border.  Choose a border radius of 5 pixels
            Iclear = imclearborder(Ithresh, 5)
            # Eliminate regions that have areas below 120 pixels
            Iopen = bwareaopen(Iclear, 120)
            # Show all images
            ##cv2.imshow('Original Image', img)
            ##cv2.imshow('Homomorphic Filtered Result', Ihmf2)
            ##cv2.imshow('Thresholded Result', Ithresh)
            ##cv2.imshow('Opened Result', Iopen)
            ##cv2.waitKey(0)
            ##cv2.destroyAllWindows()
            filtered_data.append(Iopen)
            labels.append(label)
        except:
            pass
    return filtered_data, labels

def MSER():
    """
    only draws contours around the alphabets
    """
    img = cv2.imread('data/crop_h1/I00000.png')
    mser = cv2.MSER_create()
    # Resize the image so that MSER can work better
    img = cv2.resize(img, (img.shape[1]*2, img.shape[0]*2))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    vis = img.copy()
    regions = mser.detectRegions(gray)
    hulls = [cv2.convexHull(p.reshape(-1, 1, 2)) for p in regions[0]]
    cv2.polylines(vis, hulls, 1, (0, 255, 0))
    cv2.namedWindow('img', 0)
    cv2.imshow('img', vis)
    while cv2.waitKey() != ord('q'):
        continue
    cv2.destroyAllWindows()
    cv2.imshow('Homomorphic filtered output', vis)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    # cca v1
    image = cv2.imread('data/crop_h1/I00000.png')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)

    thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)[1]

    thresh = cv2.erode(thresh, None, iterations=2)
    thresh = cv2.dilate(thresh, None, iterations=4)

    labels = measure.label(thresh, neighbors=8, background=0)
    mask = np.zeros(thresh.shape, dtype="uint8")
    # loop over the unique components
    for label in np.unique(labels):
        # if this is the background label, ignore it
        if label == 0:
            continue

        labelMask = np.zeros(thresh.shape, dtype="uint8")
        labelMask[labels == label] = 255
        numPixels = cv2.countNonZero(labelMask)
        # if the number of pixels in the component is sufficiently
        # large, then add it to our mask of "large blobs"
        if numPixels > 300:
            mask = cv2.add(mask, labelMask)
    cv2.imshow('Filtered output', mask)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def get_component(data, i, j):
    """
    returns a single component which is in the same component as i,j in the pixel
    """
    data[i][j] = 0
    req = [(i, j)]
    itr = 0
    while itr < len(req):
        x = req[itr][0]
        y = req[itr][1]
        itr += 1
        if x > 0:
            if data[x-1][y] == 255:
                data[x-1][y] = 0
                req.append((x-1, y))
            if y > 0:
                if data[x-1][y-1] == 255:
                    data[x-1][y-1] = 0
                    req.append((x-1, y-1))
            if y < len(data[0]) - 1:
                if data[x-1][y+1] == 255:
                    data[x-1][y+1] = 0
                    req.append((x-1, y+1))
        if y > 0:
            if data[x][y-1] == 255:
                data[x][y-1] = 0
                req.append((x, y-1))
        if x < len(data)-1:
            if data[x+1][y] == 255:
                data[x+1][y] = 0
                req.append((x+1, y))
            if y > 0:
                if data[x+1][y-1] == 255:
                    data[x+1][y-1] = 0
                    req.append((x+1, y-1))
            if y < len(data[0]) - 1:
                if data[x+1][y+1] == 255:
                    data[x+1][y+1] = 0
                    req.append((x+1, y+1))
        if y < len(data[0]) - 1:
            if data[x][y+1] == 255:
                data[x][y+1] = 0
                req.append((x, y+1))
        return req

def get_segments(data):
    """
    sends an array of segmented images, provided the data has only 0->black and 255->white.
    """
    segments = list()
    for i in range(len(data)):
        #for every row in the image
        for j in range(len(data[i])):
            #for every cell in a row
            if data[i][j] == 255:
                segments.append(get_component(data, i, j))
    return segments

def print_segments(segments):
    """
    use the segments and re-create the images using the segments
    """
    individual = []
    for segment in segments:
        #initialize to a very large value
        top_left_row = 100000000
        top_left_col = 100000000
        bottom_right_row = -1
        bottom_right_col = -1
        # get the top left and bottom right co-ordinates to decide the size of the component
        for (x, y) in segment:
            top_left_col = min(top_left_col, y)
            top_left_row = min(top_left_row, x)
            bottom_right_col = max(bottom_right_col, y)
            bottom_right_row = max(bottom_right_row, x)
        # create a new image with the determined size
        img = Image.new('L', (bottom_right_row - top_left_row + 1, bottom_right_col - top_left_col + 1))
        pixel = img.load()
        # initialize all the pixels to be black
        for i in range(bottom_right_row - top_left_row + 1):
            for j in range(bottom_right_col - top_left_col + 1):
                pixel[i, j] = 0
        #for all the co-ordinates in the component, set it to white
        for i in segment:
            ##print(i[0] - top_left_row," and ",i[1] - top_left_col)
            pixel[i[0] - top_left_row, i[1] - top_left_col] = 255
        #print the segment
        ##img.show()
        individual.append(img)
    return individual

def convert_image_to_numpy(individual):
    """
    convert image to array
    """
    characters = []
    for i in individual:
        inter_mediate = np.array(i)
        characters.append(inter_mediate)
    for i in characters:
        cv2.imshow('CHAR', i)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return characters

# gray scale data
##X_gray_scale, y_gray_scale = image_extraction(csv_files, 0)
# data with rgb
##X_rgb, y_rgb = image_extraction(csv_files, 1)

# saving / printing filtered data
def save_filtered_data(copy_filtered_data, labels):
    """
    save the filtered homomorphic images in images/filtered
    """
    for i in range(0, len(copy_filtered_data)):
        cv2.imwrite("images/filtered/" + labels[i] + "-" + str(i) + ".png", copy_filtered_data[i])
        cv2.imshow(str(labels[i]) + " " + str(i), copy_filtered_data[i])
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def filtered_image_extraction(files):
    """
    extract images from images/filtered
    """
    clean_data = []
    labels = []
    for file in files:
        img = cv2.imread("images/filtered/" + file, 1)
        label = file.split(sep="-")[0]
        clean_data.append(img)
        labels.append(label)
    return clean_data, labels

def noise_removal(copy_X, index):
    """
    remove the remaining noisy parts from homomorphed images
    """
    factor = 0
    for i in index:
        del copy_X[i - factor]
        factor = factor + 1
    ##return copy_X
    for i in range(0, len(copy_X)):
        file = "images/individual/" +  str(i)  + ".png"
        cv2.imwrite(file, copy_X[i])
        ##cv2.imshow(str(i), copy_X[i])
        ##cv2.waitKey(0)
        ##cv2.destroyAllWindows()

def flip_and_rotate():
    """
    flip and rotate the images
    """
    clean = []
    individual_files = os.listdir('images/individual')
    for i in range(0, len(individual_files)):
        img = cv2.imread('images/individual/' + individual_files[i])
        ##img = copy_X[i]
        img = cv2.flip(img, 1)
        clean.append(img)
    ##cv2.imshow(str(i), clean[0])
    ##cv2.waitKey(0)
    ##cv2.destroyAllWindows()
    for i in range(0, len(clean)):
        cv2.imwrite('images/clean/' + str(i) + '.png', clean[i])
    return clean

# if repository download, execute from here
# load all binary image from segregated
# grayscale load done to accomodate laoding of image as a 2d array
def final_extraction(folder_list):
    """
    extract images from all folder from training all characters
    AVAILABLE CHARACTERS - 0 1 2 3 4 5 6 7 8 9
                           A B C D E F I J L M N
                           P R S T V W X Z
    """
    X = []
    Y = []
    # iterate through each folder
    for folder in folder_list:
        file_list = os.listdir('images/segregated/' + folder)
        # iterate over all files in a folder
        for file in file_list:
            img = cv2.imread('images/segregated/' + folder + '/' + file, 0)
            X.append(img)
            Y.append(folder)
    return X, Y

# determine maximum row & column size
# to know the size to which we have to pad
def determine_max_row_and_column_size(data):
    """
    determine maximum row and column size which will
    be used for padding
    """
    max_row_size = 0
    max_col_size = 0
    for i in data:
        size = np.shape(i)
        if size[0] > max_row_size:
            max_row_size = size[0]
        if size[1] > max_col_size:
            max_col_size = size[1]
    return max_row_size, max_col_size

# padding by resizing
# we can also do a zero padding
def image_padding_by_resize(data, pad_x, pad_y):
    """
    padding by resizing
    """
    out = []
    for i in data:
        u = cv2.resize(i, (pad_x, pad_y))
        out.append(u)
    return out

def show_sample():
    """
    show the image crop_h1/I00000.png in color,
    grayscale and binary format
    """
    # an example to show difference between grayscale image and binary image
    license_plate = imread("data/crop_h1/I00000.png", as_grey=True)/255.0
    print(license_plate.shape)
    # see the difference between gray scale and binary image
    gray_car_image = license_plate * 255
    _, (ax1, ax2) = plt.subplots(1, 2)
    ax1.imshow(gray_car_image, cmap="gray")
    # threshold_otsu is an algorithm to reduce grayscale image to binary image
    threshold_value = threshold_otsu(gray_car_image)
    binary_car_image = gray_car_image > threshold_value
    ax2.imshow(binary_car_image, cmap="gray")
    print(binary_car_image)

def show_homomorphed_sample(image, n_index):
    """
    to show an homorphed image
    """
    cv2.imshow('Homomorphic filtered output', image[n_index])
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def preparing_data():
    """
    image extraction and processing
    1. Homomorphic filter is applied on all images & saved in images/filtered
    2. Segmenting the homomorphed images and extracting each
       character from the images
    3. Saving these segmented image to images/segmented
       The character has to be manually re-arranged into folders
       Each folder name is the character shown in the image
    """
    global CSV_FILES
    show_sample()
    filtered_data, filtered_labels = homomorphic_filter(CSV_FILES)
    show_homomorphed_sample(filtered_data, 578)
    ##clean_data, clean_labels = filtered_image_extraction(filtered_files)
    segments_list = []
    for each_plate in filtered_data:
        corner_y = np.shape(each_plate)[1] - 1
        corner_x = np.shape(each_plate)[0] - 1
        get_component(each_plate, 0, 0)
        get_component(each_plate, 0, corner_y)
        get_component(each_plate, corner_x, 0)
        get_component(each_plate, corner_x, corner_y)
        segments_list.append(get_segments(each_plate))
    individual_list = []
    for segments in segments_list:
        individual_list.append(print_segments(segments))
    # individual_list can be used for further processing
    # converting PIL image to numpy arrays
    individual_images = []
    for plate in individual_list:
        for char in plate:
            individual_images.append(np.array(char))
    # for labels
    labels = []
    for i in filtered_labels:
        for j in i:
            labels.append(j)
    copy_individual_images = individual_images
    # collecting index row-wise removal
    index = []
    for i in range(0, len(copy_individual_images)):
        if(np.shape(copy_individual_images[i])[0] > 40
           or np.shape(copy_individual_images[i])[0] < 15):
            index.append(i)
    # collecting index column-wise removal
    index = []
    for i in range(0, len(copy_individual_images)):
        if(np.shape(copy_individual_images[i])[1] < 15
           or np.shape(copy_individual_images[i])[1] > 100):
            index.append(i)
    # display
    for i in index:
        cv2.imshow(str(i), copy_individual_images[i])
        cv2.waitKey(0)
        cv2.destroyAllWindows()
