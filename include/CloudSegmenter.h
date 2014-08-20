#ifndef BAXTER_DEMOS_CLOUD_SEGMENTER_H_
#define BAXTER_DEMOS_CLOUD_SEGMENTER_H_

#include <iostream>
#include <exception>
#include <cmath>

#include "ros/ros.h"
#include "tf/transform_listener.h"

#include "std_msgs/Header.h"
#include "sensor_msgs/PointCloud2.h"
#include "geometry_msgs/PoseArray.h"
#include "geometry_msgs/Pose.h"
#include "geometry_msgs/Quaternion.h"

#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>
#include <pcl/point_types_conversion.h>
#include <pcl/recognition/color_gradient_dot_modality.h>
#include <pcl/common/centroid.h>
#include <pcl/common/transforms.h>
#include <pcl/filters/conditional_removal.h>
#include <pcl/filters/passthrough.h>
#include <pcl/segmentation/region_growing_rgb.h>
#include <pcl/search/search.h>
#include <pcl/search/kdtree.h>
#include <pcl/visualization/cloud_viewer.h>
#include <pcl/features/moment_of_inertia_estimation.h>

#include <pcl/conversions.h>
#include <pcl/PCLPointCloud2.h>
#include <pcl_conversions/pcl_conversions.h>


#include "OrientedBoundingBox.h"

using namespace std;

typedef pcl::PointCloud<pcl::PointXYZRGB> PointColorCloud;
typedef pair<PointColorCloud::Ptr, OrientedBoundingBox> CloudPtrBoxPair;
typedef map<PointColorCloud::Ptr, OrientedBoundingBox> CloudPtrBoxMap;

//TODO: yamlization
const string win_name = "Cloud viewer";
const float object_side = 0.06; //cheating
const float exclusion_padding = 0.01;
const int sample_size = 50;

class CloudSegmenter {
private:
    int radius;
    int filter_min;
    int filter_max;
    int distance_threshold;
    int point_color_threshold;
    int region_color_threshold;
    int min_cluster_size;

    bool has_desired_color;
    bool has_cloud;

    string frame_id;
    pcl::PointRGB desired_color;
    
    pcl::IndicesPtr indices;
    ros::NodeHandle n;
    ros::Subscriber cloud_sub;
    ros::Publisher pose_pub;
    ros::Subscriber goal_sub;
    ros::Publisher cloud_pub;

    pcl::RegionGrowingRGB<pcl::PointXYZRGB> reg;
    pcl::PointCloud<pcl::PointXYZRGB>::ConstPtr cloud;
    pcl::PointCloud <pcl::PointXYZRGB>::Ptr colored_cloud;

    vector<pcl::PointCloud<pcl::PointXYZRGB>::Ptr> cloud_ptrs;
    CloudPtrBoxMap cloud_boxes;
    vector<geometry_msgs::Pose> object_poses;
    tf::TransformListener tf_listener;


    void mergeCollidingBoxes();
    //static void addComparison(pcl::ConditionAnd<pcl::PointXYZRGB>::Ptr range_cond, const char* channel, pcl::ComparisonOps::CompareOp op, float value);

public:

    //pcl::visualization::CloudViewer cloud_viewer;
    pcl::PointCloud<pcl::PointXYZRGB>::ConstPtr getCloudPtr();
    pcl::PointCloud<pcl::PointXYZRGB>::ConstPtr getClusteredCloudPtr();
    
    bool hasCloud();
    
    bool hasColor();
    static bool isPointWithinDesiredRange(const pcl::PointRGB input_pt,
                               const pcl::PointRGB desired_pt, int radius);

    CloudSegmenter();
    void publish_poses();
    //remember to shift-click!
    void getClickedPoint(const pcl::visualization::PointPickingEvent& event,
                         void* args);
    //void renderCloud();
    //void renderClusters();
    pcl::PointRGB getCloudColorAt(int x, int y);
    pcl::PointRGB getCloudColorAt(int n);
   
    void segmentation();
    void points_callback(const sensor_msgs::PointCloud2::ConstPtr& msg);
    void goal_callback(const geometry_msgs::Pose msg);
};

#endif
