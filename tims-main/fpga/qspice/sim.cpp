#include <verilated.h>
#include <Vsim.h>

extern "C" __declspec(dllexport) void Destroy(Vsim *instance)
{
   if(instance)
      delete(instance);
}

extern "C" __declspec(dllexport) void sim(Vsim **instance, double t, union uData *data)
{
   if(!*instance)
      *instance = new Vsim;

   (*instance)->clk = data[0].b;
   (*instance)->rst = data[1].b;
   (*instance)->current1_in = data[2].i;
   (*instance)->current2_in = data[3].i;
   (*instance)->mag1_setpoint_in = data[4].i;
   (*instance)->mag2_setpoint_in = data[5].i;
   (*instance)->modulation_in = data[6].i;

   (*instance)->eval();

   data[7].b = (*instance)->pwm_ch1a;
   data[8].b = (*instance)->pwm_ch1b;
   data[9].b = (*instance)->pwm_ch1c;
   data[10].b = (*instance)->pwm_ch1d;

   data[11].b = (*instance)->pwm_ch2a;
   data[12].b = (*instance)->pwm_ch2b;
   data[13].b = (*instance)->pwm_ch2c;
   data[14].b = (*instance)->pwm_ch2d;

   data[15].i = (*instance)->mag1_out;
   data[16].i = (*instance)->phase1_out;
   data[17].i = (*instance)->mag2_out;
   data[18].i = (*instance)->phase2_out;
}
