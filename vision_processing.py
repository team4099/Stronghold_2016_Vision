#!/usr/bin/env python

import cv2
import numpy
import math
import random

import glob

B_RANGE = (20, 255)
G_RANGE = (20, 255)
R_RANGE = (20, 255)

DEFINITE_GOALS = numpy.load("contours.npy")
# print(DEFINITE_GOALS.size)

WIDTH_OF_GOAL_IN_METERS = 0.51
FOV_OF_CAMERA = math.radians(57)
VERTICAL_FOV = math.radians(43)
# FOV_OF_CAMERA = math.radians(1)
# cv2.namedWindow("Vision")


class GoalNotFoundException(Exception):
    """
    The Exception raised when there is no goal in the image
    """
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def average_goal_matching(contour):
    global DEFINITE_GOALS
    total_score = 0
    min_score = 9999999999999999
    # number_of_things = 0
    if len(contour) < 8:
        return 9999999999999999
    for definite_goal in DEFINITE_GOALS:
        # number_of_things += 1
        this_score = cv2.matchShapes(contour, definite_goal, 1, 0.0)
        # print("Score:", this_score)
        total_score += this_score
        if this_score < min_score:
            min_score = this_score
    # print(number_of_things)
    # print("Smallest score:", min_score)
    # return total_score / DEFINITE_GOALS.size
    return min_score


def threshold_image_for_tape(image):
    """
    Thresholds image for reflective tape with light shined on it. This means it
    looks for pixels that are almost white, makes them white, and makes
    everything else black.

    Parameters:
        :param: `image` - the source image to threshold from
    """
    orig_image = numpy.copy(image)
    # print orig_image.size
    orig_image = cv2.medianBlur(orig_image, 3)
    # orig_image[orig_image > 100] = 255
    # return orig_image[orig_image > 100]
    height, width = orig_image.shape[0], orig_image.shape[1]
    eight_bit_image = numpy.zeros((height, width, 1), numpy.uint8)
    cv2.inRange(orig_image,
                (B_RANGE[0], G_RANGE[0], R_RANGE[0], 0),
                (B_RANGE[1], G_RANGE[1], R_RANGE[1], 100),
                eight_bit_image)
    # # eight_bit_image = cv2.adaptiveThreshold(orig_image,
    # #                             255,
    # #                             cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    # #                             cv2.THRESH_BINARY,
    # #                             8,
    # #                             0)
    # cv2.medianBlur(eight_bit_image, 9)
    return eight_bit_image


def get_contours(orig_image):
    """
    Get edge points (hopefully corners) from the given opencv image (called
    contours in opencv)

    Parameters:
        :param: `orig_image` - the thresholded image from which to find contours
    """
    new_image = numpy.copy(orig_image)
    # cv2.imshow("Vision", new_image)
    # cv2.waitKey(1000)
    new_image, contours, hierarchy = cv2.findContours(new_image,
                                                      cv2.RETR_EXTERNAL,
                                                      cv2.CHAIN_APPROX_SIMPLE)
    # print(len(contours))
    # print(len(contours[0]))
    # print(len(contours[0][0]))
    # print(len(contours[0][0][0]))
    largest_contour = 0
    most_matching = 0
    min_score = 0
    max_area = 0
    if len(contours) > 1:
        print("Length of contours:", len(contours))
        max_area = cv2.contourArea(contours[0])
        min_score = average_goal_matching(contours[0])
        for i in range(1, len(contours)):
            # print(contours[i])
            current_score = average_goal_matching(contours[i])
            current_area = cv2.contourArea(contours[i])
            if current_area > max_area:
                max_area = current_area
                largest_contour = i
            if current_score < min_score and current_score != 0 and current_area > 300 and current_area < 1500:
                min_score = current_score
                most_matching = i
    elif len(contours) == 0:
        raise GoalNotFoundException("Goal not found!")
    if min_score >= 9999999999999999:
        raise GoalNotFoundException("Goal not found!")
    print("largest_contour:", largest_contour)
    print("Area:", max_area)
    # print("largest_contour:", largest_contour)
    print("Most matching:", most_matching)
    print("Score:", min_score)
    print("Area of most matching:", cv2.contourArea(contours[most_matching]))

    rect = cv2.minAreaRect(contours[most_matching])
    box = cv2.boxPoints(rect)
    box = numpy.int0(box)
    # print(box)
    return numpy.array(contours[most_matching]), box


def get_corners_from_contours(contours, corner_amount=4):
    """
    Finds four corners from a list of points on the goal
    epsilon - the minimum side length of the polygon generated by the corners

    Parameters:
        :param: `contours` - a numpy array of points (opencv contour) of the
                             points to get corners from
        :param: `corner_amount` - the number of corners to find
    """
    coefficient = .05
    while True:
        # print(contours)
        epsilon = coefficient * cv2.arcLength(contours, True)
        # epsilon =
        # print("epsilon:", epsilon)
        poly_approx = cv2.approxPolyDP(contours, epsilon, True)
        hull = cv2.convexHull(poly_approx)
        if len(hull) == corner_amount:
            return hull
        else:
            if len(hull) > corner_amount:
                coefficient += .01
            else:
                coefficient -= .01


def sort_corners(corners, center):
    """
    Sorts the corners in clockwise format around the center

    Parameters:
        :param: `corners` - a numpy array of coordinates of corners of the goal
        :param: `center` - a numpy array of size 2 with the center in it
    """
    top = []
    bot = []
    # print("center:", center)
    for i in range(len(corners)):
        # print("corners[i][0][1]:", corners[i][0][1])
        if(corners[i][0][1] < center[1]):
            top.append(corners[i])
        else:
            bot.append(corners[i])
    # print("top:", top)
    tl = top[1] if top[0][0][0] > top[1][0][0] else top[0]
    tr = top[0] if top[0][0][0] > top[1][0][0] else top[1]
    bl = bot[1] if bot[0][0][0] > bot[1][0][0] else bot[0]
    br = bot[0] if bot[0][0][0] > bot[1][0][0] else bot[1]
    return numpy.array([tl, tr, br, bl], numpy.float32)

def get_center(corners):
    """
    Gets center pixel of object given corner pixels
    Parameters:
        :param: `corners` - a numpy array of corner pixels
    Returns:
        A numpy array of size 2 with the x and y coords of the center
    """
    center = numpy.array([0, 0])
    for i in range(len(corners)):
        center[0] += corners[i][0][0]
        center[1] += corners[i][0][1]
    center[0] /= len(corners)
    center[1] /= len(corners)
    return center

def get_top_center(corners):
    """
    Gets center pixel of object on top line given corner pixels
    Parameters:
        :param: `corners` - a numpy array of corner pixels
    Returns:
        A numpy array of size 2 with the x and y coords of the center
    """
    center = numpy.array([0, 0])
    for i in range(len(corners)):
        center[0] += corners[i][0][0]
    center[0] /= len(corners)
    center[1] = (corners[0][0][1] + corners[1][0][1]) / 2
    return center


def get_warped_image_from_corners(image, corners):
    """
    Returns unwarped image of goal, using corners of goal and the original
    source image.
    Parameters:
        :param: `image` - the original source image with the goal in it
        :param: `corners` - a numpy array of the corner pixels of the goal

    """
    orig_image = numpy.copy(image)
    center = get_center(corners)
    corners = sort_corners(corners, center)

    height_right = int(math.sqrt((corners[1][0][0] - corners[2][0][0]) ** 2 +
                                 (corners[1][0][1] - corners[2][0][1]) ** 2))
    height_left = int(math.sqrt((corners[0][0][0] - corners[3][0][0]) ** 2 +
                                (corners[0][0][1] - corners[3][0][1]) ** 2))
    height = int((height_left + height_right) / 2)
    width = int(height * (300 / 210))

    quad = numpy.zeros((width, height))
    quad_pts = numpy.array([[[0, 0]],      [[width, 0]],
                            [[width, height]], [[0, height]]], numpy.float32)

    new_image_to_process = numpy.array(image, numpy.float32)
    quad_pts = cv2.getPerspectiveTransform(corners, quad_pts)
    warped_image = cv2.warpPerspective(new_image_to_process, quad_pts,
                                      (width, height))
    return warped_image

# def get_distance_to_goal(orig_image, warped_image):
#     angle_between_sides = (len(warped_image[0]) / len(orig_image[0])) * FOV_OF_CAMERA
#     print(math.degrees(angle_between_sides))
#     return ((WIDTH_OF_GOAL_IN_METERS / 2) / math.sin(angle_between_sides / 2)) * math.sin((math.pi + angle_between_sides) / 2)


def get_angles_to_goal(goal_center, orig_image):
    """
    Gets the angle from the top center of the goal to the center of the image.
    len(orig_image) is height; len(orig_image[0]) is width
    Parameters:
        :param: `goal_center` - a numpy array of size 2 with the
                                coords of the center
        :param: `orig_image` - the image to get the angle from
    """
    # print(goal_center)
    HEIGHT_CONVERSION_FACTOR = VERTICAL_FOV / len(orig_image)
    HORIZONTAL_CONVERSION_FACTOR = FOV_OF_CAMERA / len(orig_image[0])
    # Positive when up / right, negative when down / left
    vert_angle_rads = HEIGHT_CONVERSION_FACTOR * (-goal_center[1] + len(orig_image) / 2)
    horiz_angle_rads = HORIZONTAL_CONVERSION_FACTOR * (goal_center[0] - len(orig_image[0]) / 2)
    return (math.degrees(horiz_angle_rads), math.degrees(vert_angle_rads))


def get_kinect_angles(image):
    """
    Gets angle to goal given an opencv image.
    Parameters:
        :param: `image` - an opencv image
    """
    # print(image)
    cv2.imwrite("out/thing.png", image)
    thresholded_image = threshold_image_for_tape(numpy.copy(image))
    cv2.imwrite("out/threshold.png", thresholded_image)
    contours, box = get_contours(thresholded_image)
    # total_image = cv2.drawContours(image, [contours], -1, (0, 0, 0))
    # random_number = str(int(random.random() * 100))
    # print("random number:", random_number)
    # cv2.imwrite("out/total_image" + random_number + ".png", total_image)
    corners = get_corners_from_contours(contours)
    return get_angles_to_goal(get_top_center(corners), image)

def get_training_contours():
    # files = glob.glob("img/training*")
    # for filerino in files:
    #     img = cv2.imread(filerino)
    #     thres = threshold_image_for_tape(img)
    #     cv2.imwrite(filerino + "th.png", thres)
    thres_files = glob.glob("img/*.pngth.png")
    total_list = []
    for filerino in thres_files:
        print(filerino)
        img = cv2.imread(filerino)
        img = threshold_image_for_tape(img)
        contour, box = get_contours(img)
        # print(contour)
        total_list.append(contour)
    print(total_list)
    numpy.save("contours.npy", numpy.array(total_list))

def main(image_to_process):
    # image_to_process = cv2.imread("img/video_14528758.png")
    untouched_image = numpy.copy(image_to_process)

    thresholded_image = threshold_image_for_tape(numpy.copy(image_to_process))
    cv2.imwrite("img/thresholded.png", thresholded_image)
    contours, box = get_contours(thresholded_image)

    contoured_image = numpy.copy(untouched_image)
    contoured_image = cv2.drawContours(contoured_image, contours, -1, (0, 0, 0))
    cv2.imwrite("img/contoured.png", contoured_image)

    total_image = numpy.copy(untouched_image)
    total_image = cv2.drawContours(total_image, [box], -1, (0, 0, 0))
    cv2.imwrite("img/total_image.png", total_image)
    # x = get_corners_from_contours(contours)
    # cv2.imwrite("img/new_image.png", new_image)
    # print(type(contours))

    corners = get_corners_from_contours(contours)

    new_image = numpy.copy(untouched_image)
    new_image = cv2.drawContours(new_image, [corners], -1, (0, 0, 0))
    cv2.imwrite("img/hull_image.png", new_image)

    print(get_angles_to_goal(get_top_center(corners), untouched_image))
    # warped_image = numpy.copy(untouched_image)
    # warped_image = get_warped_image_from_corners(warped_image, corners)

    # print(get_distance_to_goal(untouched_image, warped_image))
    # total_image = cv2.drawContours(image_to_process, [corners], -1, (0, 0, 0))
    # cv2.imwrite("img/warped_image.png", warped_image)
    # print(x)
    # while 1:
    #     cv.ShowImage("Vision", image_to_process)


# main(cv2.imread("img/tower_image.png"))
if __name__ == '__main__':
    pass
    # get_training_contours()
    files = glob.glob("img/vision_testing*")
    for filerino in files:
        print()
        print("**" + filerino + "**")
        print(get_kinect_angles(cv2.imread(filerino)))
