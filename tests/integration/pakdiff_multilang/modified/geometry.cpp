#include <iostream>
#include <cmath>
#include <vector>
#include <stdexcept>
#include <memory>
#include <algorithm>

using namespace std;
using namespace std::chrono;

// Enhanced global constants
constexpr double PI = 3.141592653589793;
constexpr int MAX_POINTS = 10000;
constexpr double EPSILON = 1e-9;

// Global utility functions
template<typename T>
bool isEqual(T a, T b) {
    return abs(a - b) < EPSILON;
}

namespace geometry {
    
    class Point {
    private:
        double x, y;
        
    public:
        Point(double x = 0.0, double y = 0.0) : x(x), y(y) {
            if (!isfinite(x) || !isfinite(y)) {
                throw invalid_argument("Point coordinates must be finite");
            }
        }
        
        double getX() const { return x; }
        double getY() const { return y; }
        
        void setX(double newX) { 
            if (!isfinite(newX)) throw invalid_argument("X coordinate must be finite");
            x = newX; 
        }
        
        void setY(double newY) { 
            if (!isfinite(newY)) throw invalid_argument("Y coordinate must be finite");
            y = newY; 
        }
        
        double distance(const Point& other) const {
            double dx = x - other.x;
            double dy = y - other.y;
            return sqrt(dx*dx + dy*dy);
        }
        
        Point operator+(const Point& other) const {
            return Point(x + other.x, y + other.y);
        }
    };
    
    class Circle {
    private:
        Point center;
        double radius;
        
    public:
        Circle(Point center, double radius) : center(center), radius(radius) {
            if (radius < 0) {
                throw invalid_argument("Radius cannot be negative");
            }
        }
        
        double getArea() const {
            return PI * radius * radius;
        }
        
        double getCircumference() const {
            return 2 * PI * radius;
        }
        
        bool contains(const Point& point) const {
            return center.distance(point) <= radius + EPSILON;
        }
    };
    
    class Rectangle {
    private:
        Point topLeft;
        double width, height;
        
    public:
        Rectangle(Point topLeft, double width, double height) 
            : topLeft(topLeft), width(width), height(height) {
            if (width < 0 || height < 0) {
                throw invalid_argument("Width and height must be non-negative");
            }
        }
        
        double getArea() const {
            return width * height;
        }
        
        double getPerimeter() const {
            return 2 * (width + height);
        }
    };
    
    double calculatePerimeter(const vector<Point>& points) {
        if (points.size() < 2) {
            return 0.0;
        }
        
        double perimeter = 0.0;
        for (size_t i = 0; i < points.size() - 1; ++i) {
            perimeter += points[i].distance(points[i + 1]);
        }
        return perimeter;
    }
    
    unique_ptr<Circle> createCircle(const Point& center, double radius) {
        return make_unique<Circle>(center, radius);
    }
}