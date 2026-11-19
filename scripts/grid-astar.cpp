// Local finishing router. Input masks are produced from tscircuit copper.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <vector>
struct Entry{int f,g,id;bool operator<(const Entry&b)const{return f>b.f;}};
int main(int argc,char**argv){
 if(argc!=3)return 2;std::ifstream in(argv[1],std::ios::binary);
 int w,h,sx,sy,sl,gxmin,gymin,gxmax,gymax;int *header[]={&w,&h,&sx,&sy,&sl,&gxmin,&gymin,&gxmax,&gymax};for(auto p:header)in.read((char*)p,4);
 const int plane=w*h,n=4*plane;std::vector<uint8_t>free(n),via(plane),goal(n);in.read((char*)free.data(),n);in.read((char*)via.data(),plane);in.read((char*)goal.data(),n);
 const int groundEscapePenalty=std::getenv("ROUTING_GROUND_LAYER_COST")?std::atoi(std::getenv("ROUTING_GROUND_LAYER_COST")):(std::getenv("ROUTING_GROUND_ESCAPES")?50:0);
 const int ripPenalty=std::getenv("ROUTING_RIP_CELL_COST")?std::atoi(std::getenv("ROUTING_RIP_CELL_COST")):500;
 const int viaCost=std::getenv("ROUTING_VIA_COST")?std::atoi(std::getenv("ROUTING_VIA_COST")):200;
 const int maxExpanded=std::getenv("ROUTING_MAX_EXPANDED")?std::atoi(std::getenv("ROUTING_MAX_EXPANDED")):12000000;
 if(!in){std::cerr<<"Invalid routing masks\n";return 2;}
 std::vector<uint8_t>soft(n,0),viaSoft(plane,0);if(in.peek()!=EOF){in.read((char*)soft.data(),n);in.read((char*)viaSoft.data(),plane);}
 auto heur=[&](int x,int y){int dx=std::max({gxmin-x,0,x-gxmax}),dy=std::max({gymin-y,0,y-gymax});return 10*std::max(dx,dy)+4*std::min(dx,dy);};
 std::vector<int>dist(n,INT32_MAX),parent(n,-1);std::priority_queue<Entry>q;int start=sl*plane+sy*w+sx;dist[start]=0;q.push({heur(sx,sy),0,start});
 int found=-1,expanded=0;const int dx[]={1,0,-1,0,1,-1,-1,1},dy[]={0,1,0,-1,1,1,-1,-1};
 while(!q.empty()){
  auto cur=q.top();q.pop();if(cur.g!=dist[cur.id])continue;if(goal[cur.id]){found=cur.id;break;}if(++expanded>maxExpanded)break;
  int l=cur.id/plane,rem=cur.id%plane,y=rem/w,x=rem%w;
  for(int k=0;k<8;k++){
   int xx=x+dx[k],yy=y+dy[k];if(xx<0||xx>=w||yy<0||yy>=h)continue;
   int id=l*plane+yy*w+xx;if(!free[id])continue;
   if(k>=4&&(!free[l*plane+y*w+xx]||!free[l*plane+yy*w+x]))continue;
   int cost=cur.g+(k<4?10:14)+(l==1?groundEscapePenalty:0)+(soft[id]?ripPenalty:0);if(cost<dist[id]){dist[id]=cost;parent[id]=cur.id;q.push({cost+heur(xx,yy),cost,id});}
  }
  if(via[rem])for(int ll=0;ll<4;ll++)if(ll!=l){int id=ll*plane+rem;if(!free[id])continue;int cost=cur.g+viaCost+(viaSoft[rem]?400000:0);if(cost<dist[id]){dist[id]=cost;parent[id]=cur.id;q.push({cost+heur(x,y),cost,id});}}
 }
 std::ofstream out(argv[2]);if(found<0){
  bool exhausted=q.empty();
  out<<"{\"found\":false,\"expanded\":"<<expanded<<",\"exhausted\":"<<(exhausted?"true":"false")<<"}\n";
  if(exhausted){
   std::ofstream reachable(std::string(argv[2])+".reachable.bin",std::ios::binary);
   std::vector<uint8_t>visited(n);for(int i=0;i<n;i++)visited[i]=dist[i]!=INT32_MAX;
   reachable.write((char*)visited.data(),n);
  }
  return 1;
 }
 std::vector<int>path;for(int p=found;p>=0;p=parent[p])path.push_back(p);std::reverse(path.begin(),path.end());
 out<<"{\"found\":true,\"expanded\":"<<expanded<<",\"path\":[";
 for(size_t i=0;i<path.size();i++){int id=path[i];if(i)out<<',';out<<'['<<id%plane%w<<','<<id%plane/w<<','<<id/plane<<']';}out<<"]}\n";
}
