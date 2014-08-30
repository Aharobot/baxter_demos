#ifndef BAXTER_DEMOS_CLOUD_SEGMENTER_H_
#define BAXTER_DEMOS_CLOUD_SEGMENTER_H_

#include <iostream>
#include <exception>
#include <cmath>
#include <cstdlib>
#include <map>

#include <boost/thread/thread.hpp>
#include <boost/thread/mutex.hpp>

#include "ros/ros.h"
#include <nodelet/nodelet.h>
#include "tf/transform_listener.h"

#include "std_msgs/Header.h"
#include "sensor_msgs/PointCloud2.h"
#include "geometry_msgs/PoseArray.h"
#include "geometry_msgs/Pose.h"
#include "geometry_msgs/Point.h"
#include "geometry_msgs/Quaternion.h"
#include "moveit_msgs/CollisionObject.h"
#include <baxter_demos/CollisionObjectArray.h>

#include "OrientedBoundingBox.h"

#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>
#include <pcl/point_types_conversion.h>
#include <pcl/recognition/color_gradient_dot_modality.h>
#include <pcl/common/centroid.h>
#include <pcl/common/transforms.h>
#include <pcl/filters/conditional_removal.h>
#include <pcl/filters/passthrough.h>
#include <pcl/filters/voxel_grid.h>
#include <pcl/filters/radius_outlier_removal.h>
#include <pcl/segmentation/region_growing_rgb.h>
#include <pcl/segmentation/extract_clusters.h>
#include <pcl/search/search.h>
#include <pcl/search/kdtree.h>
#include <pcl/visualization/cloud_viewer.h>
#include <pcl/features/moment_of_inertia_estimation.h>

#include <pcl/conversions.h>
#include <pcl/PCLPointCloud2.h>
#include <pcl_conversions/pcl_conversions.h>


using namespace std;

namespace baxter_demos{

Eigen::Vector3f positionToVector(geometry_msgs::Point p);

const float threshold = 0.002;
//Compare goal poses by greater magnitude from origin
class pose_compare{
    public:
    bool operator()(geometry_msgs::Pose pose_a, geometry_msgs::Pose pose_b);
    static bool position_equal(geometry_msgs::Pose pose_a, geometry_msgs::Pose pose_b){
        return abs(pose_a.position.x - pose_b.position.x) < threshold &&
               abs(pose_a.position.y - pose_b.position.y) < threshold &&
               abs(pose_a.position.z - pose_b.position.z) < threshold;
    }
};


typedef pcl::PointCloud<pcl::PointXYZRGB> PointColorCloud;
typedef pair<PointColorCloud::Ptr, OrientedBoundingBox> CloudPtrBoxPair;
typedef map<PointColorCloud::Ptr, OrientedBoundingBox> CloudPtrBoxMap;
typedef map<string, geometry_msgs::Pose > IDPoseMap; 
typedef map<geometry_msgs::Pose, string, pose_compare > PoseIDMap; 
typedef map<string, moveit_msgs::CollisionObject > IDObjectMap; 

class CloudSegmenter : public nodelet::Nodelet {
private:
    int radius;
    int filter_min;
    int filter_max;
    int distance_threshold;
    int point_color_threshold;
    int region_color_threshold;
    int min_cluster_size;
    int max_cluster_size;
    double tolerance;
    float leaf_size;
    double outlier_radius;
    int min_neighbors;

    int object_sequence;

    bool has_desired_color;
    bool has_cloud;
    bool segmented;

    bool published_goals;

    float object_side;
    double exclusion_padding;
    int  sample_size;

    boost::mutex cloud_mutex;
    boost::thread* visualizer;

    string frame_id;
    pcl::PointRGB desired_color;
    
    pcl::IndicesPtr indices;
    ros::NodeHandle n;

    ros::Subscriber cloud_sub;
    ros::Subscriber color_sub;

    ros::Publisher object_pub;
    ros::Publisher cloud_pub;
    ros::Publisher goal_pub;

    pcl::RegionGrowingRGB<pcl::PointXYZRGB> reg;

    //Lock cloud pointer
    pcl::PointCloud<pcl::PointXYZRGB>::Ptr cloud;
    pcl::PointCloud <pcl::PointXYZRGB>::Ptr obstacle_cloud;
    pcl::PointCloud <pcl::PointXYZRGB>::Ptr colored_cloud;

    vector<pcl::PointCloud<pcl::PointXYZRGB>::Ptr> cloud_ptrs;
    CloudPtrBoxMap cloud_boxes;

    vector<geometry_msgs::Pose> goal_poses;
    //vector<moveit_msgs::CollisionObject> prev_diffs;
    //vector<moveit_msgs::CollisionObject> cur_diffs;
    IDObjectMap prev_diffs;
    IDObjectMap cur_diffs;

    IDObjectMap all_objects;

    tf::TransformListener tf_listener;

    sensor_msgs::PointCloud2 cloud_msg;

    float getFloatParam(string param_name);
    void match_prev_cur_poses(vector<geometry_msgs::Pose> cur_poses,
                              vector<moveit_msgs::CollisionObject>& next_objs,
                              vector<moveit_msgs::CollisionObject>& remove_objs  );
    void mergeCollidingBoxes();
    moveit_msgs::CollisionObject constructCollisionObject(geometry_msgs::Pose pose);
    void match_objects(vector<geometry_msgs::Pose> cur_poses);
    //static void addComparison(pcl::ConditionAnd<pcl::PointXYZRGB>::Ptr range_cond, const char* channel, pcl::ComparisonOps::CompareOp op, float value);
    void updateParams();

public:

    //pcl::visualization::CloudViewer cloud_viewer;
    CloudSegmenter();

    pcl::PointCloud<pcl::PointXYZRGB>::ConstPtr getCloudPtr();
    pcl::PointCloud<pcl::PointXYZRGB>::ConstPtr getDisplayCloudPtr();
    pcl::PointCloud<pcl::PointXYZRGB>::ConstPtr getClusteredCloudPtr();
    
    bool hasCloud();
    bool hasColor();
    bool wasSegmented();

    Eigen::Vector3i getDesiredColor();

    static bool isPointWithinDesiredRange(const pcl::PointRGB input_pt,
                               const pcl::PointRGB desired_pt, int radius);

    void onInit();
    void publish_poses();
    void mouseoverCallback(const pcl::visualization::MouseEvent event, void* args);
    //remember to shift-click!
    void getClickedPoint(const pcl::visualization::PointPickingEvent& event,
                         void* args);
    pcl::PointRGB getCloudColorAt(int x, int y);
    pcl::PointRGB getCloudColorAt(size_t n);
   
    void segmentation();
    void points_callback(const sensor_msgs::PointCloud2::ConstPtr& msg);
    void color_callback(const geometry_msgs::Point msg);


    void exclude_object(const geometry_msgs::Pose object,
                        const PointColorCloud::ConstPtr src_cloud,
                        PointColorCloud::Ptr dst_cloud );
    void exclude_all_objects(vector<geometry_msgs::Pose> cur_poses);
    void goal_callback(const geometry_msgs::Pose msg);
};


}


#endif
