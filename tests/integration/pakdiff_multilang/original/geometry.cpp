#include <iostream>
#include <cmath>
#include <vector>

using namespace std;

// Global constants
const double PI = 3.14159265359;
const int MAX_POINTS = 1000;

namespace geometry {
    
    class Point {
    private:
        double x, y;
        
    public:
        Point(double x, double y) : x(x), y(y) {}
        
        double getX() const { return x; }
        double getY() const { return y; }
        
        double distance(const Point& other) const {
            double dx = x - other.x;
            double dy = y - other.y;
            return sqrt(dx*dx + dy*dy);
        }
    };
    
    class Circle {
    private:
        Point center;
        double radius;
        
    public:
        Circle(Point center, double radius) : center(center), radius(radius) {}
        
        double getArea() const {
            return PI * radius * radius;
        }
    };
    
    double calculatePerimeter(const vector<Point>& points) {
        double perimeter = 0.0;
        for (size_t i = 0; i < points.size() - 1; ++i) {
            perimeter += points[i].distance(points[i + 1]);
        }
        return perimeter;
    }
}