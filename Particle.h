#ifndef PARTICLE_H
#define PARTICLE_H
class Particle{
    private:
        double mass;
        double x,y,vx,vy,ax,ay;

    public:
        Particle(double m, double x0, double y0, double vx0 = 0, double vy0 = 0);
        void setAcceleration(double ax0, double ay0);
        void addAcceleration(double dax, double day);
        void resetAcceleration();

        void kick(double dt);
        void drift(double dt);

        double getMass() const;
        double getX() const;
        double getY() const;
        double getVx() const;
        double getVy() const;
        double getAx() const;
        double getAy() const;

};

#endif