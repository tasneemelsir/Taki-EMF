var Ss=Object.defineProperty;var Ms=(n,t,e)=>t in n?Ss(n,t,{enumerable:!0,configurable:!0,writable:!0,value:e}):n[t]=e;var P=(n,t,e)=>Ms(n,typeof t!="symbol"?t+"":t,e);import{c as Se,r as ke,C as Es,b as pt,a as Ts,u as nt,d as R,e as Zt,f as Cs,g as yt,j as c,S as de,B as ht,R as Ps,M as Ds,h as zs,L as As,i as js,k as Le,l as ks,m as Ls,N as Be,n as Bs,T as Fs,P as Os}from"./index-DjuDnjjD.js";import{C as Rs,V as k,M as Tt,T as Mt,Q as Fe,S as Oe,a as J,R as Ns,P as Us,b as Ke,c as Me,d as ee,U as Qe,e as se,I as Is,F as tt,f as ve,g as Et,W as Hs,B as Ee,h as Je,i as G,j as Wt,L as Ws,k as ts,l as ie,m as Gs,n as mt,o as zt,G as ne,p as ct,D as Ht,q as Ct,r as Pt,s as ft,t as Te,u as oe,v as Ce,w as es,E as $s,x as Vs,y as ss,z as is,A as Ys,H as Zs,J as qs,K as ae,N as Xs,O as Ks,X as Qs,Y as Js,Z as ti,_ as ei,$ as si,a0 as ii,a1 as ni,a2 as oi,a3 as Re,a4 as ai,a5 as ri,a6 as li,a7 as Ne,a8 as hi}from"./three-Bk_H1X2E.js";import"./plotly-TwPhzy26.js";/**
 * @license lucide-react v0.469.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const Ue=Se("ChevronDown",[["path",{d:"m6 9 6 6 6-6",key:"qrunsl"}]]);/**
 * @license lucide-react v0.469.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const ci=Se("ChevronUp",[["path",{d:"m18 15-6-6-6 6",key:"153udz"}]]);/**
 * @license lucide-react v0.469.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const di=Se("Maximize2",[["polyline",{points:"15 3 21 3 21 9",key:"mznyad"}],["polyline",{points:"9 21 3 21 3 15",key:"1avn1i"}],["line",{x1:"21",x2:"14",y1:"3",y2:"10",key:"ota7mn"}],["line",{x1:"3",x2:"10",y1:"21",y2:"14",key:"1atl0r"}]]);function rt(n,t,e,s,i){s=s<0?0:s>t-1?t-1:s,i=i<0?0:i>e-1?e-1:i;const r=Math.min(t-2,Math.floor(s)),o=Math.min(e-2,Math.floor(i)),a=s-r,l=i-o,h=o*t+r;return(n[h]*(1-a)+n[h+1]*a)*(1-l)+(n[h+t]*(1-a)+n[h+t+1]*a)*l}function qt(n){let t=0;for(let e=0;e<n.length;e++)n[e]>t&&(t=n[e]);return t}function ui(n,t){if(!(n>0)||!(t.max>0))return 0;if(t.mode==="log"){const e=t.logDecades??3;return Math.max(0,Math.min(1,1+Math.log10(n/t.max)/e))}return Math.max(0,Math.min(1,n/t.max))}const ns=[[255,234,70],[255,178,48],[240,104,34],[198,40,58],[126,26,112]],pi=[0,150,140],fi=[56,225,212],mi=[190,45,36],gi=[251,113,133];function Ie(n,t,e){const s=n.width,i=n.height,r=n.getContext("2d"),o=r.createImageData(s,i),a=o.data,l=new Float32Array(s*i),{nx:h,ny:w,a0:u,aS:x}=t,_=(h-1)/(s-1),C=(w-1)/(i-1),p=e.view==="diff",d=e.view!=="without";for(let g=0;g<i;g++){const S=(i-1-g)*C,f=d&&(e.shieldAll||(e.rowMask?e.rowMask[g]===1:!1));for(let y=0;y<s;y++){const M=y*_,v=rt(u,h,w,M,S),E=f?rt(x,h,w,M,S):v,b=g*s+y,A=b*4;if(p){const B=v>1e-12?(E-v)/v:0;l[b]=E;const H=Math.min(1,Math.abs(B)*1.4),T=B<0?e.dark?fi:pi:e.dark?gi:mi;a[A]=T[0],a[A+1]=T[1],a[A+2]=T[2],a[A+3]=Math.round(255*e.alphaHi*Math.pow(H,.75))}else{const B=e.view==="with"?E:v;l[b]=B;const H=ui(B,e),L=e.mode!=="log"&&B>e.max?ke(Math.min(1,Math.log10(B/e.max)/2),ns):ke(H,Es),F=Math.min(1,H/.4),z=e.alphaLo+(e.alphaHi-e.alphaLo)*F*F*(3-2*F);a[A]=L[0],a[A+1]=L[1],a[A+2]=L[2],a[A+3]=Math.round(255*z)}}}for(const g of e.contours){if(!(g.level>0))continue;const S=g.level;for(let f=0;f<i-1;f++)for(let y=0;y<s-1;y++){const M=f*s+y,v=l[M]>=S;(v!==l[M+1]>=S||v!==l[M+s]>=S)&&(ue(a,M,g.color,g.alpha??1),g.bold&&(ue(a,M+1,g.color,1),ue(a,M+s,g.color,1)))}}r.putImageData(o,0,0)}function ue(n,t,e,s){const i=t*4;if(s>=1){n[i]=e[0],n[i+1]=e[1],n[i+2]=e[2],n[i+3]=255;return}const r=n[i+3]/255,o=s+r*(1-s);for(let a=0;a<3;a++)n[i+a]=Math.round((e[a]*s+n[i+a]*r*(1-s))/Math.max(o,1e-6));n[i+3]=Math.round(o*255)}function wi(n,t,e=6){if(!(t>0)||!(n>0)||n>=t)return[];const s=[];for(let i=Math.floor(Math.log10(n));i<=Math.ceil(Math.log10(t));i++)for(const r of[1,2,5]){const o=r*Math.pow(10,i);o>n*1.001&&o<t*.999&&s.push(o)}for(;s.length>e;)s.splice(0,1);return s}const He={type:"change"},Pe={type:"start"},os={type:"end"},Xt=new Ns,We=new Us,yi=Math.cos(70*Ke.DEG2RAD),$=new k,Q=2*Math.PI,O={NONE:-1,ROTATE:0,DOLLY:1,PAN:2,TOUCH_ROTATE:3,TOUCH_PAN:4,TOUCH_DOLLY_PAN:5,TOUCH_DOLLY_ROTATE:6},pe=1e-6;class xi extends Rs{constructor(t,e=null){super(t,e),this.state=O.NONE,this.enabled=!0,this.target=new k,this.cursor=new k,this.minDistance=0,this.maxDistance=1/0,this.minZoom=0,this.maxZoom=1/0,this.minTargetRadius=0,this.maxTargetRadius=1/0,this.minPolarAngle=0,this.maxPolarAngle=Math.PI,this.minAzimuthAngle=-1/0,this.maxAzimuthAngle=1/0,this.enableDamping=!1,this.dampingFactor=.05,this.enableZoom=!0,this.zoomSpeed=1,this.enableRotate=!0,this.rotateSpeed=1,this.enablePan=!0,this.panSpeed=1,this.screenSpacePanning=!0,this.keyPanSpeed=7,this.zoomToCursor=!1,this.autoRotate=!1,this.autoRotateSpeed=2,this.keys={LEFT:"ArrowLeft",UP:"ArrowUp",RIGHT:"ArrowRight",BOTTOM:"ArrowDown"},this.mouseButtons={LEFT:Tt.ROTATE,MIDDLE:Tt.DOLLY,RIGHT:Tt.PAN},this.touches={ONE:Mt.ROTATE,TWO:Mt.DOLLY_PAN},this.target0=this.target.clone(),this.position0=this.object.position.clone(),this.zoom0=this.object.zoom,this._domElementKeyEvents=null,this._lastPosition=new k,this._lastQuaternion=new Fe,this._lastTargetPosition=new k,this._quat=new Fe().setFromUnitVectors(t.up,new k(0,1,0)),this._quatInverse=this._quat.clone().invert(),this._spherical=new Oe,this._sphericalDelta=new Oe,this._scale=1,this._panOffset=new k,this._rotateStart=new J,this._rotateEnd=new J,this._rotateDelta=new J,this._panStart=new J,this._panEnd=new J,this._panDelta=new J,this._dollyStart=new J,this._dollyEnd=new J,this._dollyDelta=new J,this._dollyDirection=new k,this._mouse=new J,this._performCursorZoom=!1,this._pointers=[],this._pointerPositions={},this._controlActive=!1,this._onPointerMove=bi.bind(this),this._onPointerDown=vi.bind(this),this._onPointerUp=_i.bind(this),this._onContextMenu=Di.bind(this),this._onMouseWheel=Ei.bind(this),this._onKeyDown=Ti.bind(this),this._onTouchStart=Ci.bind(this),this._onTouchMove=Pi.bind(this),this._onMouseDown=Si.bind(this),this._onMouseMove=Mi.bind(this),this._interceptControlDown=zi.bind(this),this._interceptControlUp=Ai.bind(this),this.domElement!==null&&this.connect(),this.update()}connect(){this.domElement.addEventListener("pointerdown",this._onPointerDown),this.domElement.addEventListener("pointercancel",this._onPointerUp),this.domElement.addEventListener("contextmenu",this._onContextMenu),this.domElement.addEventListener("wheel",this._onMouseWheel,{passive:!1}),this.domElement.getRootNode().addEventListener("keydown",this._interceptControlDown,{passive:!0,capture:!0}),this.domElement.style.touchAction="none"}disconnect(){this.domElement.removeEventListener("pointerdown",this._onPointerDown),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.domElement.removeEventListener("pointercancel",this._onPointerUp),this.domElement.removeEventListener("wheel",this._onMouseWheel),this.domElement.removeEventListener("contextmenu",this._onContextMenu),this.stopListenToKeyEvents(),this.domElement.getRootNode().removeEventListener("keydown",this._interceptControlDown,{capture:!0}),this.domElement.style.touchAction="auto"}dispose(){this.disconnect()}getPolarAngle(){return this._spherical.phi}getAzimuthalAngle(){return this._spherical.theta}getDistance(){return this.object.position.distanceTo(this.target)}listenToKeyEvents(t){t.addEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=t}stopListenToKeyEvents(){this._domElementKeyEvents!==null&&(this._domElementKeyEvents.removeEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=null)}saveState(){this.target0.copy(this.target),this.position0.copy(this.object.position),this.zoom0=this.object.zoom}reset(){this.target.copy(this.target0),this.object.position.copy(this.position0),this.object.zoom=this.zoom0,this.object.updateProjectionMatrix(),this.dispatchEvent(He),this.update(),this.state=O.NONE}update(t=null){const e=this.object.position;$.copy(e).sub(this.target),$.applyQuaternion(this._quat),this._spherical.setFromVector3($),this.autoRotate&&this.state===O.NONE&&this._rotateLeft(this._getAutoRotationAngle(t)),this.enableDamping?(this._spherical.theta+=this._sphericalDelta.theta*this.dampingFactor,this._spherical.phi+=this._sphericalDelta.phi*this.dampingFactor):(this._spherical.theta+=this._sphericalDelta.theta,this._spherical.phi+=this._sphericalDelta.phi);let s=this.minAzimuthAngle,i=this.maxAzimuthAngle;isFinite(s)&&isFinite(i)&&(s<-Math.PI?s+=Q:s>Math.PI&&(s-=Q),i<-Math.PI?i+=Q:i>Math.PI&&(i-=Q),s<=i?this._spherical.theta=Math.max(s,Math.min(i,this._spherical.theta)):this._spherical.theta=this._spherical.theta>(s+i)/2?Math.max(s,this._spherical.theta):Math.min(i,this._spherical.theta)),this._spherical.phi=Math.max(this.minPolarAngle,Math.min(this.maxPolarAngle,this._spherical.phi)),this._spherical.makeSafe(),this.enableDamping===!0?this.target.addScaledVector(this._panOffset,this.dampingFactor):this.target.add(this._panOffset),this.target.sub(this.cursor),this.target.clampLength(this.minTargetRadius,this.maxTargetRadius),this.target.add(this.cursor);let r=!1;if(this.zoomToCursor&&this._performCursorZoom||this.object.isOrthographicCamera)this._spherical.radius=this._clampDistance(this._spherical.radius);else{const o=this._spherical.radius;this._spherical.radius=this._clampDistance(this._spherical.radius*this._scale),r=o!=this._spherical.radius}if($.setFromSpherical(this._spherical),$.applyQuaternion(this._quatInverse),e.copy(this.target).add($),this.object.lookAt(this.target),this.enableDamping===!0?(this._sphericalDelta.theta*=1-this.dampingFactor,this._sphericalDelta.phi*=1-this.dampingFactor,this._panOffset.multiplyScalar(1-this.dampingFactor)):(this._sphericalDelta.set(0,0,0),this._panOffset.set(0,0,0)),this.zoomToCursor&&this._performCursorZoom){let o=null;if(this.object.isPerspectiveCamera){const a=$.length();o=this._clampDistance(a*this._scale);const l=a-o;this.object.position.addScaledVector(this._dollyDirection,l),this.object.updateMatrixWorld(),r=!!l}else if(this.object.isOrthographicCamera){const a=new k(this._mouse.x,this._mouse.y,0);a.unproject(this.object);const l=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),this.object.updateProjectionMatrix(),r=l!==this.object.zoom;const h=new k(this._mouse.x,this._mouse.y,0);h.unproject(this.object),this.object.position.sub(h).add(a),this.object.updateMatrixWorld(),o=$.length()}else console.warn("WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled."),this.zoomToCursor=!1;o!==null&&(this.screenSpacePanning?this.target.set(0,0,-1).transformDirection(this.object.matrix).multiplyScalar(o).add(this.object.position):(Xt.origin.copy(this.object.position),Xt.direction.set(0,0,-1).transformDirection(this.object.matrix),Math.abs(this.object.up.dot(Xt.direction))<yi?this.object.lookAt(this.target):(We.setFromNormalAndCoplanarPoint(this.object.up,this.target),Xt.intersectPlane(We,this.target))))}else if(this.object.isOrthographicCamera){const o=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),o!==this.object.zoom&&(this.object.updateProjectionMatrix(),r=!0)}return this._scale=1,this._performCursorZoom=!1,r||this._lastPosition.distanceToSquared(this.object.position)>pe||8*(1-this._lastQuaternion.dot(this.object.quaternion))>pe||this._lastTargetPosition.distanceToSquared(this.target)>pe?(this.dispatchEvent(He),this._lastPosition.copy(this.object.position),this._lastQuaternion.copy(this.object.quaternion),this._lastTargetPosition.copy(this.target),!0):!1}_getAutoRotationAngle(t){return t!==null?Q/60*this.autoRotateSpeed*t:Q/60/60*this.autoRotateSpeed}_getZoomScale(t){const e=Math.abs(t*.01);return Math.pow(.95,this.zoomSpeed*e)}_rotateLeft(t){this._sphericalDelta.theta-=t}_rotateUp(t){this._sphericalDelta.phi-=t}_panLeft(t,e){$.setFromMatrixColumn(e,0),$.multiplyScalar(-t),this._panOffset.add($)}_panUp(t,e){this.screenSpacePanning===!0?$.setFromMatrixColumn(e,1):($.setFromMatrixColumn(e,0),$.crossVectors(this.object.up,$)),$.multiplyScalar(t),this._panOffset.add($)}_pan(t,e){const s=this.domElement;if(this.object.isPerspectiveCamera){const i=this.object.position;$.copy(i).sub(this.target);let r=$.length();r*=Math.tan(this.object.fov/2*Math.PI/180),this._panLeft(2*t*r/s.clientHeight,this.object.matrix),this._panUp(2*e*r/s.clientHeight,this.object.matrix)}else this.object.isOrthographicCamera?(this._panLeft(t*(this.object.right-this.object.left)/this.object.zoom/s.clientWidth,this.object.matrix),this._panUp(e*(this.object.top-this.object.bottom)/this.object.zoom/s.clientHeight,this.object.matrix)):(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - pan disabled."),this.enablePan=!1)}_dollyOut(t){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale/=t:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_dollyIn(t){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale*=t:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_updateZoomParameters(t,e){if(!this.zoomToCursor)return;this._performCursorZoom=!0;const s=this.domElement.getBoundingClientRect(),i=t-s.left,r=e-s.top,o=s.width,a=s.height;this._mouse.x=i/o*2-1,this._mouse.y=-(r/a)*2+1,this._dollyDirection.set(this._mouse.x,this._mouse.y,1).unproject(this.object).sub(this.object.position).normalize()}_clampDistance(t){return Math.max(this.minDistance,Math.min(this.maxDistance,t))}_handleMouseDownRotate(t){this._rotateStart.set(t.clientX,t.clientY)}_handleMouseDownDolly(t){this._updateZoomParameters(t.clientX,t.clientX),this._dollyStart.set(t.clientX,t.clientY)}_handleMouseDownPan(t){this._panStart.set(t.clientX,t.clientY)}_handleMouseMoveRotate(t){this._rotateEnd.set(t.clientX,t.clientY),this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);const e=this.domElement;this._rotateLeft(Q*this._rotateDelta.x/e.clientHeight),this._rotateUp(Q*this._rotateDelta.y/e.clientHeight),this._rotateStart.copy(this._rotateEnd),this.update()}_handleMouseMoveDolly(t){this._dollyEnd.set(t.clientX,t.clientY),this._dollyDelta.subVectors(this._dollyEnd,this._dollyStart),this._dollyDelta.y>0?this._dollyOut(this._getZoomScale(this._dollyDelta.y)):this._dollyDelta.y<0&&this._dollyIn(this._getZoomScale(this._dollyDelta.y)),this._dollyStart.copy(this._dollyEnd),this.update()}_handleMouseMovePan(t){this._panEnd.set(t.clientX,t.clientY),this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd),this.update()}_handleMouseWheel(t){this._updateZoomParameters(t.clientX,t.clientY),t.deltaY<0?this._dollyIn(this._getZoomScale(t.deltaY)):t.deltaY>0&&this._dollyOut(this._getZoomScale(t.deltaY)),this.update()}_handleKeyDown(t){let e=!1;switch(t.code){case this.keys.UP:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateUp(Q*this.rotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,this.keyPanSpeed),e=!0;break;case this.keys.BOTTOM:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateUp(-Q*this.rotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,-this.keyPanSpeed),e=!0;break;case this.keys.LEFT:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateLeft(Q*this.rotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(this.keyPanSpeed,0),e=!0;break;case this.keys.RIGHT:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateLeft(-Q*this.rotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(-this.keyPanSpeed,0),e=!0;break}e&&(t.preventDefault(),this.update())}_handleTouchStartRotate(t){if(this._pointers.length===1)this._rotateStart.set(t.pageX,t.pageY);else{const e=this._getSecondPointerPosition(t),s=.5*(t.pageX+e.x),i=.5*(t.pageY+e.y);this._rotateStart.set(s,i)}}_handleTouchStartPan(t){if(this._pointers.length===1)this._panStart.set(t.pageX,t.pageY);else{const e=this._getSecondPointerPosition(t),s=.5*(t.pageX+e.x),i=.5*(t.pageY+e.y);this._panStart.set(s,i)}}_handleTouchStartDolly(t){const e=this._getSecondPointerPosition(t),s=t.pageX-e.x,i=t.pageY-e.y,r=Math.sqrt(s*s+i*i);this._dollyStart.set(0,r)}_handleTouchStartDollyPan(t){this.enableZoom&&this._handleTouchStartDolly(t),this.enablePan&&this._handleTouchStartPan(t)}_handleTouchStartDollyRotate(t){this.enableZoom&&this._handleTouchStartDolly(t),this.enableRotate&&this._handleTouchStartRotate(t)}_handleTouchMoveRotate(t){if(this._pointers.length==1)this._rotateEnd.set(t.pageX,t.pageY);else{const s=this._getSecondPointerPosition(t),i=.5*(t.pageX+s.x),r=.5*(t.pageY+s.y);this._rotateEnd.set(i,r)}this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);const e=this.domElement;this._rotateLeft(Q*this._rotateDelta.x/e.clientHeight),this._rotateUp(Q*this._rotateDelta.y/e.clientHeight),this._rotateStart.copy(this._rotateEnd)}_handleTouchMovePan(t){if(this._pointers.length===1)this._panEnd.set(t.pageX,t.pageY);else{const e=this._getSecondPointerPosition(t),s=.5*(t.pageX+e.x),i=.5*(t.pageY+e.y);this._panEnd.set(s,i)}this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd)}_handleTouchMoveDolly(t){const e=this._getSecondPointerPosition(t),s=t.pageX-e.x,i=t.pageY-e.y,r=Math.sqrt(s*s+i*i);this._dollyEnd.set(0,r),this._dollyDelta.set(0,Math.pow(this._dollyEnd.y/this._dollyStart.y,this.zoomSpeed)),this._dollyOut(this._dollyDelta.y),this._dollyStart.copy(this._dollyEnd);const o=(t.pageX+e.x)*.5,a=(t.pageY+e.y)*.5;this._updateZoomParameters(o,a)}_handleTouchMoveDollyPan(t){this.enableZoom&&this._handleTouchMoveDolly(t),this.enablePan&&this._handleTouchMovePan(t)}_handleTouchMoveDollyRotate(t){this.enableZoom&&this._handleTouchMoveDolly(t),this.enableRotate&&this._handleTouchMoveRotate(t)}_addPointer(t){this._pointers.push(t.pointerId)}_removePointer(t){delete this._pointerPositions[t.pointerId];for(let e=0;e<this._pointers.length;e++)if(this._pointers[e]==t.pointerId){this._pointers.splice(e,1);return}}_isTrackingPointer(t){for(let e=0;e<this._pointers.length;e++)if(this._pointers[e]==t.pointerId)return!0;return!1}_trackPointer(t){let e=this._pointerPositions[t.pointerId];e===void 0&&(e=new J,this._pointerPositions[t.pointerId]=e),e.set(t.pageX,t.pageY)}_getSecondPointerPosition(t){const e=t.pointerId===this._pointers[0]?this._pointers[1]:this._pointers[0];return this._pointerPositions[e]}_customWheelEvent(t){const e=t.deltaMode,s={clientX:t.clientX,clientY:t.clientY,deltaY:t.deltaY};switch(e){case 1:s.deltaY*=16;break;case 2:s.deltaY*=100;break}return t.ctrlKey&&!this._controlActive&&(s.deltaY*=10),s}}function vi(n){this.enabled!==!1&&(this._pointers.length===0&&(this.domElement.setPointerCapture(n.pointerId),this.domElement.addEventListener("pointermove",this._onPointerMove),this.domElement.addEventListener("pointerup",this._onPointerUp)),!this._isTrackingPointer(n)&&(this._addPointer(n),n.pointerType==="touch"?this._onTouchStart(n):this._onMouseDown(n)))}function bi(n){this.enabled!==!1&&(n.pointerType==="touch"?this._onTouchMove(n):this._onMouseMove(n))}function _i(n){switch(this._removePointer(n),this._pointers.length){case 0:this.domElement.releasePointerCapture(n.pointerId),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.dispatchEvent(os),this.state=O.NONE;break;case 1:const t=this._pointers[0],e=this._pointerPositions[t];this._onTouchStart({pointerId:t,pageX:e.x,pageY:e.y});break}}function Si(n){let t;switch(n.button){case 0:t=this.mouseButtons.LEFT;break;case 1:t=this.mouseButtons.MIDDLE;break;case 2:t=this.mouseButtons.RIGHT;break;default:t=-1}switch(t){case Tt.DOLLY:if(this.enableZoom===!1)return;this._handleMouseDownDolly(n),this.state=O.DOLLY;break;case Tt.ROTATE:if(n.ctrlKey||n.metaKey||n.shiftKey){if(this.enablePan===!1)return;this._handleMouseDownPan(n),this.state=O.PAN}else{if(this.enableRotate===!1)return;this._handleMouseDownRotate(n),this.state=O.ROTATE}break;case Tt.PAN:if(n.ctrlKey||n.metaKey||n.shiftKey){if(this.enableRotate===!1)return;this._handleMouseDownRotate(n),this.state=O.ROTATE}else{if(this.enablePan===!1)return;this._handleMouseDownPan(n),this.state=O.PAN}break;default:this.state=O.NONE}this.state!==O.NONE&&this.dispatchEvent(Pe)}function Mi(n){switch(this.state){case O.ROTATE:if(this.enableRotate===!1)return;this._handleMouseMoveRotate(n);break;case O.DOLLY:if(this.enableZoom===!1)return;this._handleMouseMoveDolly(n);break;case O.PAN:if(this.enablePan===!1)return;this._handleMouseMovePan(n);break}}function Ei(n){this.enabled===!1||this.enableZoom===!1||this.state!==O.NONE||(n.preventDefault(),this.dispatchEvent(Pe),this._handleMouseWheel(this._customWheelEvent(n)),this.dispatchEvent(os))}function Ti(n){this.enabled!==!1&&this._handleKeyDown(n)}function Ci(n){switch(this._trackPointer(n),this._pointers.length){case 1:switch(this.touches.ONE){case Mt.ROTATE:if(this.enableRotate===!1)return;this._handleTouchStartRotate(n),this.state=O.TOUCH_ROTATE;break;case Mt.PAN:if(this.enablePan===!1)return;this._handleTouchStartPan(n),this.state=O.TOUCH_PAN;break;default:this.state=O.NONE}break;case 2:switch(this.touches.TWO){case Mt.DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchStartDollyPan(n),this.state=O.TOUCH_DOLLY_PAN;break;case Mt.DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchStartDollyRotate(n),this.state=O.TOUCH_DOLLY_ROTATE;break;default:this.state=O.NONE}break;default:this.state=O.NONE}this.state!==O.NONE&&this.dispatchEvent(Pe)}function Pi(n){switch(this._trackPointer(n),this.state){case O.TOUCH_ROTATE:if(this.enableRotate===!1)return;this._handleTouchMoveRotate(n),this.update();break;case O.TOUCH_PAN:if(this.enablePan===!1)return;this._handleTouchMovePan(n),this.update();break;case O.TOUCH_DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchMoveDollyPan(n),this.update();break;case O.TOUCH_DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchMoveDollyRotate(n),this.update();break;default:this.state=O.NONE}}function Di(n){this.enabled!==!1&&n.preventDefault()}function zi(n){n.key==="Control"&&(this._controlActive=!0,this.domElement.getRootNode().addEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function Ai(n){n.key==="Control"&&(this._controlActive=!1,this.domElement.getRootNode().removeEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}se.line={worldUnits:{value:1},linewidth:{value:1},resolution:{value:new J(1,1)},dashOffset:{value:0},dashScale:{value:1},dashSize:{value:1},gapSize:{value:1}};ee.line={uniforms:Qe.merge([se.common,se.fog,se.line]),vertexShader:`
		#include <common>
		#include <color_pars_vertex>
		#include <fog_pars_vertex>
		#include <logdepthbuf_pars_vertex>
		#include <clipping_planes_pars_vertex>

		uniform float linewidth;
		uniform vec2 resolution;

		attribute vec3 instanceStart;
		attribute vec3 instanceEnd;

		attribute vec3 instanceColorStart;
		attribute vec3 instanceColorEnd;

		#ifdef WORLD_UNITS

			varying vec4 worldPos;
			varying vec3 worldStart;
			varying vec3 worldEnd;

			#ifdef USE_DASH

				varying vec2 vUv;

			#endif

		#else

			varying vec2 vUv;

		#endif

		#ifdef USE_DASH

			uniform float dashScale;
			attribute float instanceDistanceStart;
			attribute float instanceDistanceEnd;
			varying float vLineDistance;

		#endif

		void trimSegment( const in vec4 start, inout vec4 end ) {

			// trim end segment so it terminates between the camera plane and the near plane

			// conservative estimate of the near plane
			float a = projectionMatrix[ 2 ][ 2 ]; // 3nd entry in 3th column
			float b = projectionMatrix[ 3 ][ 2 ]; // 3nd entry in 4th column
			float nearEstimate = - 0.5 * b / a;

			float alpha = ( nearEstimate - start.z ) / ( end.z - start.z );

			end.xyz = mix( start.xyz, end.xyz, alpha );

		}

		void main() {

			#ifdef USE_COLOR

				vColor.xyz = ( position.y < 0.5 ) ? instanceColorStart : instanceColorEnd;

			#endif

			#ifdef USE_DASH

				vLineDistance = ( position.y < 0.5 ) ? dashScale * instanceDistanceStart : dashScale * instanceDistanceEnd;
				vUv = uv;

			#endif

			float aspect = resolution.x / resolution.y;

			// camera space
			vec4 start = modelViewMatrix * vec4( instanceStart, 1.0 );
			vec4 end = modelViewMatrix * vec4( instanceEnd, 1.0 );

			#ifdef WORLD_UNITS

				worldStart = start.xyz;
				worldEnd = end.xyz;

			#else

				vUv = uv;

			#endif

			// special case for perspective projection, and segments that terminate either in, or behind, the camera plane
			// clearly the gpu firmware has a way of addressing this issue when projecting into ndc space
			// but we need to perform ndc-space calculations in the shader, so we must address this issue directly
			// perhaps there is a more elegant solution -- WestLangley

			bool perspective = ( projectionMatrix[ 2 ][ 3 ] == - 1.0 ); // 4th entry in the 3rd column

			if ( perspective ) {

				if ( start.z < 0.0 && end.z >= 0.0 ) {

					trimSegment( start, end );

				} else if ( end.z < 0.0 && start.z >= 0.0 ) {

					trimSegment( end, start );

				}

			}

			// clip space
			vec4 clipStart = projectionMatrix * start;
			vec4 clipEnd = projectionMatrix * end;

			// ndc space
			vec3 ndcStart = clipStart.xyz / clipStart.w;
			vec3 ndcEnd = clipEnd.xyz / clipEnd.w;

			// direction
			vec2 dir = ndcEnd.xy - ndcStart.xy;

			// account for clip-space aspect ratio
			dir.x *= aspect;
			dir = normalize( dir );

			#ifdef WORLD_UNITS

				vec3 worldDir = normalize( end.xyz - start.xyz );
				vec3 tmpFwd = normalize( mix( start.xyz, end.xyz, 0.5 ) );
				vec3 worldUp = normalize( cross( worldDir, tmpFwd ) );
				vec3 worldFwd = cross( worldDir, worldUp );
				worldPos = position.y < 0.5 ? start: end;

				// height offset
				float hw = linewidth * 0.5;
				worldPos.xyz += position.x < 0.0 ? hw * worldUp : - hw * worldUp;

				// don't extend the line if we're rendering dashes because we
				// won't be rendering the endcaps
				#ifndef USE_DASH

					// cap extension
					worldPos.xyz += position.y < 0.5 ? - hw * worldDir : hw * worldDir;

					// add width to the box
					worldPos.xyz += worldFwd * hw;

					// endcaps
					if ( position.y > 1.0 || position.y < 0.0 ) {

						worldPos.xyz -= worldFwd * 2.0 * hw;

					}

				#endif

				// project the worldpos
				vec4 clip = projectionMatrix * worldPos;

				// shift the depth of the projected points so the line
				// segments overlap neatly
				vec3 clipPose = ( position.y < 0.5 ) ? ndcStart : ndcEnd;
				clip.z = clipPose.z * clip.w;

			#else

				vec2 offset = vec2( dir.y, - dir.x );
				// undo aspect ratio adjustment
				dir.x /= aspect;
				offset.x /= aspect;

				// sign flip
				if ( position.x < 0.0 ) offset *= - 1.0;

				// endcaps
				if ( position.y < 0.0 ) {

					offset += - dir;

				} else if ( position.y > 1.0 ) {

					offset += dir;

				}

				// adjust for linewidth
				offset *= linewidth;

				// adjust for clip-space to screen-space conversion // maybe resolution should be based on viewport ...
				offset /= resolution.y;

				// select end
				vec4 clip = ( position.y < 0.5 ) ? clipStart : clipEnd;

				// back to clip space
				offset *= clip.w;

				clip.xy += offset;

			#endif

			gl_Position = clip;

			vec4 mvPosition = ( position.y < 0.5 ) ? start : end; // this is an approximation

			#include <logdepthbuf_vertex>
			#include <clipping_planes_vertex>
			#include <fog_vertex>

		}
		`,fragmentShader:`
		uniform vec3 diffuse;
		uniform float opacity;
		uniform float linewidth;

		#ifdef USE_DASH

			uniform float dashOffset;
			uniform float dashSize;
			uniform float gapSize;

		#endif

		varying float vLineDistance;

		#ifdef WORLD_UNITS

			varying vec4 worldPos;
			varying vec3 worldStart;
			varying vec3 worldEnd;

			#ifdef USE_DASH

				varying vec2 vUv;

			#endif

		#else

			varying vec2 vUv;

		#endif

		#include <common>
		#include <color_pars_fragment>
		#include <fog_pars_fragment>
		#include <logdepthbuf_pars_fragment>
		#include <clipping_planes_pars_fragment>

		vec2 closestLineToLine(vec3 p1, vec3 p2, vec3 p3, vec3 p4) {

			float mua;
			float mub;

			vec3 p13 = p1 - p3;
			vec3 p43 = p4 - p3;

			vec3 p21 = p2 - p1;

			float d1343 = dot( p13, p43 );
			float d4321 = dot( p43, p21 );
			float d1321 = dot( p13, p21 );
			float d4343 = dot( p43, p43 );
			float d2121 = dot( p21, p21 );

			float denom = d2121 * d4343 - d4321 * d4321;

			float numer = d1343 * d4321 - d1321 * d4343;

			mua = numer / denom;
			mua = clamp( mua, 0.0, 1.0 );
			mub = ( d1343 + d4321 * ( mua ) ) / d4343;
			mub = clamp( mub, 0.0, 1.0 );

			return vec2( mua, mub );

		}

		void main() {

			#include <clipping_planes_fragment>

			#ifdef USE_DASH

				if ( vUv.y < - 1.0 || vUv.y > 1.0 ) discard; // discard endcaps

				if ( mod( vLineDistance + dashOffset, dashSize + gapSize ) > dashSize ) discard; // todo - FIX

			#endif

			float alpha = opacity;

			#ifdef WORLD_UNITS

				// Find the closest points on the view ray and the line segment
				vec3 rayEnd = normalize( worldPos.xyz ) * 1e5;
				vec3 lineDir = worldEnd - worldStart;
				vec2 params = closestLineToLine( worldStart, worldEnd, vec3( 0.0, 0.0, 0.0 ), rayEnd );

				vec3 p1 = worldStart + lineDir * params.x;
				vec3 p2 = rayEnd * params.y;
				vec3 delta = p1 - p2;
				float len = length( delta );
				float norm = len / linewidth;

				#ifndef USE_DASH

					#ifdef USE_ALPHA_TO_COVERAGE

						float dnorm = fwidth( norm );
						alpha = 1.0 - smoothstep( 0.5 - dnorm, 0.5 + dnorm, norm );

					#else

						if ( norm > 0.5 ) {

							discard;

						}

					#endif

				#endif

			#else

				#ifdef USE_ALPHA_TO_COVERAGE

					// artifacts appear on some hardware if a derivative is taken within a conditional
					float a = vUv.x;
					float b = ( vUv.y > 0.0 ) ? vUv.y - 1.0 : vUv.y + 1.0;
					float len2 = a * a + b * b;
					float dlen = fwidth( len2 );

					if ( abs( vUv.y ) > 1.0 ) {

						alpha = 1.0 - smoothstep( 1.0 - dlen, 1.0 + dlen, len2 );

					}

				#else

					if ( abs( vUv.y ) > 1.0 ) {

						float a = vUv.x;
						float b = ( vUv.y > 0.0 ) ? vUv.y - 1.0 : vUv.y + 1.0;
						float len2 = a * a + b * b;

						if ( len2 > 1.0 ) discard;

					}

				#endif

			#endif

			vec4 diffuseColor = vec4( diffuse, alpha );

			#include <logdepthbuf_fragment>
			#include <color_fragment>

			gl_FragColor = vec4( diffuseColor.rgb, alpha );

			#include <tonemapping_fragment>
			#include <colorspace_fragment>
			#include <fog_fragment>
			#include <premultiplied_alpha_fragment>

		}
		`};class as extends Me{constructor(t){super({type:"LineMaterial",uniforms:Qe.clone(ee.line.uniforms),vertexShader:ee.line.vertexShader,fragmentShader:ee.line.fragmentShader,clipping:!0}),this.isLineMaterial=!0,this.setValues(t)}get color(){return this.uniforms.diffuse.value}set color(t){this.uniforms.diffuse.value=t}get worldUnits(){return"WORLD_UNITS"in this.defines}set worldUnits(t){t===!0?this.defines.WORLD_UNITS="":delete this.defines.WORLD_UNITS}get linewidth(){return this.uniforms.linewidth.value}set linewidth(t){this.uniforms.linewidth&&(this.uniforms.linewidth.value=t)}get dashed(){return"USE_DASH"in this.defines}set dashed(t){t===!0!==this.dashed&&(this.needsUpdate=!0),t===!0?this.defines.USE_DASH="":delete this.defines.USE_DASH}get dashScale(){return this.uniforms.dashScale.value}set dashScale(t){this.uniforms.dashScale.value=t}get dashSize(){return this.uniforms.dashSize.value}set dashSize(t){this.uniforms.dashSize.value=t}get dashOffset(){return this.uniforms.dashOffset.value}set dashOffset(t){this.uniforms.dashOffset.value=t}get gapSize(){return this.uniforms.gapSize.value}set gapSize(t){this.uniforms.gapSize.value=t}get opacity(){return this.uniforms.opacity.value}set opacity(t){this.uniforms&&(this.uniforms.opacity.value=t)}get resolution(){return this.uniforms.resolution.value}set resolution(t){this.uniforms.resolution.value.copy(t)}get alphaToCoverage(){return"USE_ALPHA_TO_COVERAGE"in this.defines}set alphaToCoverage(t){this.defines&&(t===!0!==this.alphaToCoverage&&(this.needsUpdate=!0),t===!0?this.defines.USE_ALPHA_TO_COVERAGE="":delete this.defines.USE_ALPHA_TO_COVERAGE)}}const Ge=new Ee,Kt=new k;class rs extends Is{constructor(){super(),this.isLineSegmentsGeometry=!0,this.type="LineSegmentsGeometry";const t=[-1,2,0,1,2,0,-1,1,0,1,1,0,-1,0,0,1,0,0,-1,-1,0,1,-1,0],e=[-1,2,1,2,-1,1,1,1,-1,-1,1,-1,-1,-2,1,-2],s=[0,2,1,2,3,1,2,4,3,4,5,3,4,6,5,6,7,5];this.setIndex(s),this.setAttribute("position",new tt(t,3)),this.setAttribute("uv",new tt(e,2))}applyMatrix4(t){const e=this.attributes.instanceStart,s=this.attributes.instanceEnd;return e!==void 0&&(e.applyMatrix4(t),s.applyMatrix4(t),e.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this}setPositions(t){let e;t instanceof Float32Array?e=t:Array.isArray(t)&&(e=new Float32Array(t));const s=new ve(e,6,1);return this.setAttribute("instanceStart",new Et(s,3,0)),this.setAttribute("instanceEnd",new Et(s,3,3)),this.instanceCount=this.attributes.instanceStart.count,this.computeBoundingBox(),this.computeBoundingSphere(),this}setColors(t){let e;t instanceof Float32Array?e=t:Array.isArray(t)&&(e=new Float32Array(t));const s=new ve(e,6,1);return this.setAttribute("instanceColorStart",new Et(s,3,0)),this.setAttribute("instanceColorEnd",new Et(s,3,3)),this}fromWireframeGeometry(t){return this.setPositions(t.attributes.position.array),this}fromEdgesGeometry(t){return this.setPositions(t.attributes.position.array),this}fromMesh(t){return this.fromWireframeGeometry(new Hs(t.geometry)),this}fromLineSegments(t){const e=t.geometry;return this.setPositions(e.attributes.position.array),this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new Ee);const t=this.attributes.instanceStart,e=this.attributes.instanceEnd;t!==void 0&&e!==void 0&&(this.boundingBox.setFromBufferAttribute(t),Ge.setFromBufferAttribute(e),this.boundingBox.union(Ge))}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new Je),this.boundingBox===null&&this.computeBoundingBox();const t=this.attributes.instanceStart,e=this.attributes.instanceEnd;if(t!==void 0&&e!==void 0){const s=this.boundingSphere.center;this.boundingBox.getCenter(s);let i=0;for(let r=0,o=t.count;r<o;r++)Kt.fromBufferAttribute(t,r),i=Math.max(i,s.distanceToSquared(Kt)),Kt.fromBufferAttribute(e,r),i=Math.max(i,s.distanceToSquared(Kt));this.boundingSphere.radius=Math.sqrt(i),isNaN(this.boundingSphere.radius)&&console.error("THREE.LineSegmentsGeometry.computeBoundingSphere(): Computed radius is NaN. The instanced position data is likely to have NaN values.",this)}}toJSON(){}applyMatrix(t){return console.warn("THREE.LineSegmentsGeometry: applyMatrix() has been renamed to applyMatrix4()."),this.applyMatrix4(t)}}const fe=new Wt,$e=new k,Ve=new k,V=new Wt,Y=new Wt,ot=new Wt,me=new k,ge=new ts,Z=new Ws,Ye=new k,Qt=new Ee,Jt=new Je,at=new Wt;let lt,xt;function Ze(n,t,e){return at.set(0,0,-t,1).applyMatrix4(n.projectionMatrix),at.multiplyScalar(1/at.w),at.x=xt/e.width,at.y=xt/e.height,at.applyMatrix4(n.projectionMatrixInverse),at.multiplyScalar(1/at.w),Math.abs(Math.max(at.x,at.y))}function ji(n,t){const e=n.matrixWorld,s=n.geometry,i=s.attributes.instanceStart,r=s.attributes.instanceEnd,o=Math.min(s.instanceCount,i.count);for(let a=0,l=o;a<l;a++){Z.start.fromBufferAttribute(i,a),Z.end.fromBufferAttribute(r,a),Z.applyMatrix4(e);const h=new k,w=new k;lt.distanceSqToSegment(Z.start,Z.end,w,h),w.distanceTo(h)<xt*.5&&t.push({point:w,pointOnLine:h,distance:lt.origin.distanceTo(w),object:n,face:null,faceIndex:a,uv:null,uv1:null})}}function ki(n,t,e){const s=t.projectionMatrix,r=n.material.resolution,o=n.matrixWorld,a=n.geometry,l=a.attributes.instanceStart,h=a.attributes.instanceEnd,w=Math.min(a.instanceCount,l.count),u=-t.near;lt.at(1,ot),ot.w=1,ot.applyMatrix4(t.matrixWorldInverse),ot.applyMatrix4(s),ot.multiplyScalar(1/ot.w),ot.x*=r.x/2,ot.y*=r.y/2,ot.z=0,me.copy(ot),ge.multiplyMatrices(t.matrixWorldInverse,o);for(let x=0,_=w;x<_;x++){if(V.fromBufferAttribute(l,x),Y.fromBufferAttribute(h,x),V.w=1,Y.w=1,V.applyMatrix4(ge),Y.applyMatrix4(ge),V.z>u&&Y.z>u)continue;if(V.z>u){const f=V.z-Y.z,y=(V.z-u)/f;V.lerp(Y,y)}else if(Y.z>u){const f=Y.z-V.z,y=(Y.z-u)/f;Y.lerp(V,y)}V.applyMatrix4(s),Y.applyMatrix4(s),V.multiplyScalar(1/V.w),Y.multiplyScalar(1/Y.w),V.x*=r.x/2,V.y*=r.y/2,Y.x*=r.x/2,Y.y*=r.y/2,Z.start.copy(V),Z.start.z=0,Z.end.copy(Y),Z.end.z=0;const p=Z.closestPointToPointParameter(me,!0);Z.at(p,Ye);const d=Ke.lerp(V.z,Y.z,p),g=d>=-1&&d<=1,S=me.distanceTo(Ye)<xt*.5;if(g&&S){Z.start.fromBufferAttribute(l,x),Z.end.fromBufferAttribute(h,x),Z.start.applyMatrix4(o),Z.end.applyMatrix4(o);const f=new k,y=new k;lt.distanceSqToSegment(Z.start,Z.end,y,f),e.push({point:y,pointOnLine:f,distance:lt.origin.distanceTo(y),object:n,face:null,faceIndex:x,uv:null,uv1:null})}}}class Li extends G{constructor(t=new rs,e=new as({color:Math.random()*16777215})){super(t,e),this.isLineSegments2=!0,this.type="LineSegments2"}computeLineDistances(){const t=this.geometry,e=t.attributes.instanceStart,s=t.attributes.instanceEnd,i=new Float32Array(2*e.count);for(let o=0,a=0,l=e.count;o<l;o++,a+=2)$e.fromBufferAttribute(e,o),Ve.fromBufferAttribute(s,o),i[a]=a===0?0:i[a-1],i[a+1]=i[a]+$e.distanceTo(Ve);const r=new ve(i,2,1);return t.setAttribute("instanceDistanceStart",new Et(r,1,0)),t.setAttribute("instanceDistanceEnd",new Et(r,1,1)),this}raycast(t,e){const s=this.material.worldUnits,i=t.camera;i===null&&!s&&console.error('LineSegments2: "Raycaster.camera" needs to be set in order to raycast against LineSegments2 while worldUnits is set to false.');const r=t.params.Line2!==void 0&&t.params.Line2.threshold||0;lt=t.ray;const o=this.matrixWorld,a=this.geometry,l=this.material;xt=l.linewidth+r,a.boundingSphere===null&&a.computeBoundingSphere(),Jt.copy(a.boundingSphere).applyMatrix4(o);let h;if(s)h=xt*.5;else{const u=Math.max(i.near,Jt.distanceToPoint(lt.origin));h=Ze(i,u,l.resolution)}if(Jt.radius+=h,lt.intersectsSphere(Jt)===!1)return;a.boundingBox===null&&a.computeBoundingBox(),Qt.copy(a.boundingBox).applyMatrix4(o);let w;if(s)w=xt*.5;else{const u=Math.max(i.near,Qt.distanceToPoint(lt.origin));w=Ze(i,u,l.resolution)}Qt.expandByScalar(w),lt.intersectsBox(Qt)!==!1&&(s?ji(this,e):ki(this,i,e))}onBeforeRender(t){const e=this.material.uniforms;e&&e.resolution&&(t.getViewport(fe),this.material.uniforms.resolution.value.set(fe.z,fe.w))}}function qe(n){return n?{dark:n,ground:"#101B29",grid:"#1A293B",gridMajor:"#27405B",steel:"#A3B3C4",pole:"#B4C0CC",insulator:"#D2BC8E",phase:{A:"#F0685A",B:"#F2C230",C:"#5AA9F5"},teal:"#38D6CB",tealBright:"#5FF0E6",row:"#4DA3FF",ink:"#E6EDF4",edge:"#05090F",glass:"#16263A",glassLit:"#F4CF7A",violet:"#B594E6",red:"#F2776E",roof:"#2A3646",plant:"#3A4656"}:{dark:n,ground:"#E8EDF0",grid:"#D6DEE4",gridMajor:"#BECAD3",steel:"#5B6770",pole:"#7E8A93",insulator:"#8A6F4E",phase:{A:"#C0392B",B:"#D9A400",C:"#004B87"},teal:"#00857C",tealBright:"#00B8B0",row:"#004B87",ink:"#0F1B24",edge:"#0F1B24",glass:"#8FA9BE",glassLit:"#B9CBDA",violet:"#6B3FA0",red:"#B3261E",roof:"#A9B2B9",plant:"#8D979F"}}const I=(n,t,e)=>Math.max(t,Math.min(e,n));function et(n,t,e,s,i,r,o){n.push(t,e,s,i,r,o)}function Bi(n){return I(n/100+.5,1.2,5)}function be(n){const t=Bi(n.kv),s=Math.max(...n.conductors.map(i=>i.y_att))+t+.8;return{ins:t,body:s,top:s+I(n.kv/80,2,6)}}function Fi(n,t,e,s){const i=n.xc,{ins:r,body:o,top:a}=be(n),l=new Map;for(const p of n.conductors){const d=Math.round(p.y_att*2)/2;l.has(d)||l.set(d,[]),l.get(d).push(p)}if(n.tower==="monopole"){const p=I(a*.022,.45,1.1),d=.26,g=new G(new ie(d,p,o+1.2,14),new Gs({color:s.pole,metalness:.35,roughness:.55}));g.position.set(i,(o+1.2)/2,t),g.castShadow=!0,e.meshes.push(g);const S=new G(new ie(p*1.9,p*1.9,.35,16),new mt({color:s.plant}));S.position.set(i,.17,t),e.meshes.push(S);for(const[,f]of l){const y=f[0].y_att+r;for(const M of[-1,1]){const v=f.filter(E=>(E.x-i)*M>.5).sort((E,b)=>(b.x-E.x)*M)[0];v&&et(e.arms,i,y-I(Math.abs(v.x-i)*.16,.4,1.4),t,v.x,y,t)}for(const M of f)et(e.insul,M.x,y,t,M.x,M.y_att,t)}return}const h=I(o*.105,2,5.5),w=I(n.kv/400,.6,1.2),u=p=>h+(w-h)*I(p/o,0,1),x=Math.max(4,Math.round(o/5)),_=e.lattice,C=[[-1,-1],[1,-1],[1,1],[-1,1]];for(let p=0;p<x;p++){const d=o*p/x,g=o*(p+1)/x,S=u(d),f=u(g);for(let y=0;y<4;y++){const[M,v]=C[y],[E,b]=C[(y+1)%4];et(_,i+M*S,d,t+v*S,i+M*f,g,t+v*f),et(_,i+M*f,g,t+v*f,i+E*f,g,t+b*f),et(_,i+M*S,d,t+v*S,i+E*f,g,t+b*f),et(_,i+E*S,d,t+b*S,i+M*f,g,t+v*f)}}for(const[p,d]of C)et(_,i+p*w,o,t+d*w,i,a,t);for(const[p,d]of C){const g=new G(new zt(.9,.5,.9),new mt({color:s.plant}));g.position.set(i+p*h,.25,t+d*h),e.meshes.push(g)}for(const[,p]of l){const d=p[0].y_att+r;for(const g of[-1,1]){const S=p.filter(b=>(b.x-i)*g>u(d)+.2).sort((b,A)=>(A.x-b.x)*g)[0];if(!S)continue;const f=Math.abs(S.x-i),y=I(f*.26,1,3.2),M=u(d),v=u(d+y);for(const b of[-1,1])et(_,i+g*M,d,t+b*M,S.x,d,t),et(_,i+g*v,d+y,t+b*v,S.x,d,t);const E=i+g*(M+(f-M)*.5);et(_,E,d,t,i+g*(v+(f-v)*.5),d+y*.5,t)}for(const g of p)et(e.insul,g.x,d,t,g.x,g.y_att,t)}}function Oi(n,t,e){const s={A:[],B:[],C:[],off:[]},i={A:[],B:[],C:[],off:[]},r=44,o=12;for(const a of n.conductors){const l=a.bundle.length?a.bundle:[[0,0]],h=a.y_att-a.y;for(const[w,u]of l){const x=a.x+w,_=a.on===!1?"off":a.phase,C=s[_]??s.A;let p=a.y_att+u,d=-t;for(let S=1;S<=r;S++){const f=-t+2*t*S/r,y=a.y+h*(f/t)*(f/t)+u;C.push(x,p,d,x,y,f),p=y,d=f}const g=i[_]??i.A;for(const S of[-1,1]){let f=a.y_att+u,y=S*t;for(let M=1;M<=o;M++){const v=e*M/o,E=(v-t)/t,b=a.y+h*E*E+u,A=S*(t+v);g.push(x,f,y,x,b,A),f=b,y=A}}}}return{main:s,stub:i}}function Ri(n,t,e,s){const a=document.createElement("canvas");a.width=a.height=256;const l=a.getContext("2d");l.fillStyle=n,l.fillRect(0,0,256,256);const h=64*I(.3+t*.62,.3,.9),w=64*I(.34+t*.42,.34,.78);let u=s*9301+49297;const x=()=>(u=(u*9301+49297)%233280,u/233280);for(let C=0;C<4;C++){l.fillStyle="rgba(0,0,0,0.10)",l.fillRect(0,C*64,256,2);for(let p=0;p<4;p++){const d=p*64+(64-h)/2,g=C*64+(64-w)/2+2,S=e.dark?x()<.3:x()<.5;l.fillStyle=S?e.glassLit:e.glass,l.fillRect(d,g,h,w),l.strokeStyle="rgba(0,0,0,0.28)",l.lineWidth=1.5,l.strokeRect(d,g,h,w),h>64*.5&&(l.beginPath(),l.moveTo(d+h/2,g),l.lineTo(d+h/2,g+w),l.stroke())}}const _=new oe(a);return _.colorSpace=Ce,_.wrapS=_.wrapT=es,_.anisotropy=4,_}function Ni(n,t){const e=new Te(n);return e.multiplyScalar(t),`#${e.getHexString()}`}function we(n,t,e){const s=n.clone();return s.repeat.set(Math.max(.25,t),Math.max(.25,e)),s.needsUpdate=!0,new mt({map:s})}function It(n,t){const e=new Ct(new $s(n.geometry,20),new Pt({color:t.edge,transparent:!0,opacity:t.dark?.55:.3}));return n.add(e),n.castShadow=!0,n.receiveShadow=!0,n}function Ui(n,t,e){var M,v;const s=new ne;s.name=`building:${e}`;const i=t.dark?Ni(n.color,.42):n.color,r=Ri(i,n.glazing,t,e+3),o=new mt({color:t.roof}),a=n.x0+n.w/2,l=n.z,h=Math.max(2.4,n.floor_h||3.2),w=4,u=(E,b,A,B,H,T)=>{const L=Math.max(1,Math.round(b/h))/4,F=we(r,A/w/4,L),z=we(r,E/w/4,L),N=new G(new zt(E,b,A),[F,F,o,o,z,z]);return N.position.set(B,H+b/2,T),s.add(It(N,t)),N};let x=n.h,_=0;n.roof==="pitched"&&(_=I(Math.min(n.w,n.d)*.22,1.2,n.h*.34),x=n.h-_),n.roof==="stepped"&&(x=Math.max(h,n.h-h));let C=n.w,p=n.d,d=a,g=l;if(n.shape==="cylinder"){const E=Math.min(n.w,n.d)/2,b=Math.max(1,Math.round(x/h))/4,A=we(r,2*Math.PI*E/w/4,b),B=new G(new ie(E,E,x,40),[A,o,o]);B.position.set(a,x/2,l),s.add(It(B,t)),C=p=E*1.3}else if(n.shape==="lshape"){u(n.w,x,n.d*.5,a,0,l-n.d*.25);const E=n.w*.45,b=n.side==="left"?n.x0+n.w-E/2:n.x0+E/2;u(E,x,n.d*.5,b,0,l+n.d*.25),p=n.d*.5,g=l-n.d*.25}else if(n.shape==="multistory"){const E=Math.min(x*.3,2*h);u(n.w,E,n.d,a,0,l),C=n.w*.62,p=n.d*.7,u(C,x-E,p,a,E,l)}else u(n.w,x,n.d,a,0,l);if(n.roof==="pitched"&&n.shape!=="cylinder"){const E=C>=p,b=C/2+.4,A=p/2+.4,B=E?[[-b,0,-A],[b,0,-A],[b,0,A],[-b,0,A],[-b,_,0],[b,_,0]]:[[-b,0,-A],[-b,0,A],[b,0,A],[b,0,-A],[0,_,-A],[0,_,A]],H=[[0,1,5],[0,5,4],[3,4,5],[3,5,2],[0,4,3],[1,2,5]],T=[];for(const z of H)for(const N of z)T.push(B[N][0],B[N][1],B[N][2]);const L=new ct;L.setAttribute("position",new tt(T,3)),L.computeVertexNormals();const F=new G(L,new mt({color:t.dark?"#4A3530":"#9B5B48",side:Ht}));F.position.set(d,x,g),s.add(It(F,t))}else if(n.roof==="stepped")u(C*.56,n.h-x,p*.56,d,x,g);else if((n.plant||(M=n.rooftop)!=null&&M.length)&&!/data|warehouse/i.test(n.type)){const E=I((((v=n.rooftop)==null?void 0:v.length)||1)+1,2,4);for(let b=0;b<E;b++){const A=I(C*.12,1.2,4),B=I(p*.16,1.2,4),H=1.1+.35*(b%2),T=new G(new zt(A,H,B),new mt({color:t.plant}));T.position.set(d-C*.3+C*.6*b/Math.max(1,E-1),x+H/2,g+(b%2?1:-1)*p*.18),s.add(It(T,t))}}const S=1,f=Math.min(n.w,n.d)/2,y={x:n.shape==="cylinder"?a+f:n.x0+n.w,z:n.shape==="lshape"?l-n.d*.25:l,len:n.shape==="cylinder"?f*.9:n.shape==="lshape"?n.d*.5:n.d,sx:S,wallH:x,fh:h};return Ii(s,n,t,y,{x:d,z:g,w:C,d:p,y:n.roof==="pitched"?x:n.h,rise:_}),s}function Ii(n,t,e,s,i){const r=d=>new mt({color:d}),o=r(e.dark?"#0B1422":"#33414E"),a=r(e.dark?"#5A6878":"#EEF1F3"),l=r(e.plant),h=(d,g,S,f,y,M,v,E=!1)=>{const b=new G(new zt(d,g,S),v);return b.position.set(f,y,M),b.castShadow=!0,n.add(E?It(b,e):b),b},w=(d,g,S,f,y,M,v,E=18)=>{const b=new G(new ie(d,g,S,E),v);return b.position.set(f,y,M),b.castShadow=!0,n.add(b),b},u=d=>s.x+s.sx*d,x=t.type.toLowerCase(),_=Math.min(2.4,s.wallH*.8);if(x.includes("warehouse")){const d=I(Math.floor(s.len/9),1,5),g=Math.min(4.2,s.len/(d+1)),S=Math.min(4.6,s.wallH*.7);for(let f=0;f<d;f++){const y=s.z-s.len/2+s.len*(f+.5)/d;h(.14,S,g,u(.07),S/2,y,a,!0);for(let M=1;M<5;M++)h(.16,.05,g,u(.08),S*M/5,y,o);h(.9,.5,g+.8,u(.45),.25,y,l)}if(i.rise>0){const f=i.w>=i.d;h(f?i.w*.7:1,.45,f?1:i.d*.7,i.x,i.y+i.rise+.2,i.z,a,!0)}return}const C=x.includes("school")||x.includes("hospital")||x.includes("office")?I(s.len*.16,2.4,6):1.2;h(.12,_,C,u(.06),_/2,s.z,o),h(.14,_,.08,u(.07),_/2,s.z,a);const p=x.includes("school")||x.includes("hospital")?3.2:1.1;if(h(p,.18,C+1.2,u(p/2),_+.35,s.z,a,!0),p>2)for(const d of[-1,1])w(.11,.11,_+.3,u(p-.3),(_+.3)/2,s.z+d*(C+.7)/2,a,10);if(x.includes("residential")){const d=I(Math.round(s.wallH/s.fh),1,14),g=s.len>=9?[-.27,.27]:[0];for(let S=1;S<d;S++)for(const f of g){const y=s.z+f*s.len,M=S*s.fh;h(1.2,.14,2.6,u(.6),M,y,a,!0),h(.05,.9,2.6,u(1.18),M+.5,y,o);for(const v of[-1,1])h(1.2,.9,.05,u(.6),M+.5,y+v*1.3,o)}i.rise>0&&h(.8,i.rise*.9+.8,.8,i.x+i.w*.22,i.y+i.rise*.45+.4,i.z+i.d*.18,r(e.dark?"#3A2A26":"#7C4A3A"),!0)}else if(x.includes("office"))w(.07,.11,I(t.h*.22,3,9),i.x+i.w*.34,i.y+I(t.h*.22,3,9)/2,i.z-i.d*.3,l,8);else if(x.includes("school")){const d=I(t.h*.8,5,10);w(.05,.07,d,u(5),d/2,s.z+C/2+3,l,8),h(.04,.7,1.1,u(5),d-.5,s.z+C/2+3.6,r(e.dark?"#3E77B3":"#004B87"))}else if(x.includes("hospital")){const d=t.roof==="stepped",g=d?i.w*.56:i.w,S=d?i.d*.56:i.d,f=I(Math.min(g,S)*.36,2,7);w(f,f,.16,i.x,i.y+.08,i.z,r(e.dark?"#27384A":"#7F8C97"),32);const y=new G(new Vs(f*.78,f*.9,40),new ft({color:"#FFFFFF",side:Ht}));y.rotation.x=-Math.PI/2,y.position.set(i.x,i.y+.18,i.z),n.add(y);const M=new ft({color:"#FFFFFF"});for(const v of[-1,1])h(f*.12,.03,f*.8,i.x+v*f*.26,i.y+.18,i.z,M);h(f*.52,.03,f*.12,i.x,i.y+.18,i.z,M)}else if(x.includes("data")){for(let y=0;y<3;y++)h(.1,.35,s.len*.8,u(.05),s.wallH*(.45+.17*y),s.z,o);const d=I(Math.floor(i.w/6),2,8),g=I(i.w/d*.62,1.6,4.2),S=I(i.d*.2,1.6,4);for(let y=0;y<d;y++){const M=i.x-i.w/2+i.w*(y+.5)/d,v=i.z-i.d*.24;h(g,1.5,S,M,i.y+.75,v,l,!0);for(const E of[-1,1])w(Math.min(g,S)*.2,Math.min(g,S)*.2,.12,M+E*g/4,i.y+1.56,v,o,14)}const f=I(Math.min(i.w,i.d)*.09,1.1,2.6);for(const y of[-1,1])w(f*.8,f,f*1.9,i.x+y*i.w*.2,i.y+f*.95,i.z+i.d*.24,l,22),w(f*.62,f*.62,.1,i.x+y*i.w*.2,i.y+f*1.9+.02,i.z+i.d*.24,o,22)}}function Hi(n){const t=document.createElement("canvas");t.width=t.height=64;const e=t.getContext("2d");e.clearRect(0,0,64,64),e.strokeStyle=n.tealBright,e.lineWidth=5,e.strokeRect(0,0,64,64);const s=new oe(t);return s.colorSpace=Ce,s.wrapS=s.wrapT=es,s}function Wi(n,t,e){const s=new ne;s.name="shield";const i={group:s,wires:[],bonds:[]};if(!n.on||!n.walls.length)return i;const r=Math.max(-e,n.zc-n.zh),o=Math.min(e,n.zc+n.zh);if(n.is_wire){const T=[];for(const[z,N]of n.wires){i.wires.push(z,N,r,z,N,o);for(const U of[r,o])T.push(z,0,U,z,N,U)}const L=[];if(n.preset==="passive-loop")for(let z=0;z+1<n.wires.length;z+=2)L.push([n.wires[z],n.wires[z+1]]);else{const z=n.wires.filter(U=>U[0]>=0),N=n.wires.filter(U=>U[0]<0);for(const U of[z,N])U.length>1&&L.push([...U].sort((W,dt)=>W[0]-dt[0]))}if(n.bonded)for(const z of L)for(const N of[r,o])for(let U=0;U+1<z.length;U++)i.bonds.push(z[U][0],z[U][1],N,z[U+1][0],z[U+1][1],N);const F=new ct;return F.setAttribute("position",new tt(T,3)),s.add(new Ct(F,new Pt({color:t.steel,transparent:!0,opacity:.7}))),i}const a=n.mesh?Hi(t):null,l=[],h=[],w=[],u=[],x=1.5,_=(T,L,F,z,N,U)=>{l.push(...T,...L,...F,...T,...F,...z),h.push(0,0,N,0,N,U,0,0,N,U,0,U),w.push(...T,...L,...L,...F,...F,...z,...z,...T)};let C=1/0,p=-1/0,d=1/0,g=-1/0;for(const[T,L,F,z]of n.walls)C=Math.min(C,T,F),p=Math.max(p,T,F),d=Math.min(d,L,z),g=Math.max(g,L,z);const S=n.attached&&!n.room&&n.preset!=="surround-wall"?.18:0,f=(C+p)/2,y=T=>S&&Math.abs(T-f)>1e-6?T+Math.sign(T-f)*S:T,M=T=>S&&T>d+.5&&Math.abs(T-g)<1e-6?T+S:T,v=r-S,E=o+S;for(const[T,L,F,z]of n.walls){const N=Math.hypot(F-T,z-L);if(_([y(T),M(L),v],[y(F),M(z),v],[y(F),M(z),E],[y(T),M(L),E],N/x,(E-v)/x),Math.abs(T-F)<.05&&Math.min(L,z)<.3&&!n.attached){const U=Math.max(1,Math.round((o-r)/10));for(let W=0;W<=U;W++){const dt=r+(o-r)*W/U;u.push(T,0,dt,T,Math.max(L,z)+.4,dt)}}}if(n.surrounding)for(const T of[v,E])_([y(C),d,T],[y(p),d,T],[y(p),M(g),T],[y(C),M(g),T],(p-C)/x,(g-d)/x);const b=new ct;b.setAttribute("position",new tt(l,3)),b.setAttribute("uv",new tt(h,2));const A=new ft({color:a?"#ffffff":t.teal,map:a,transparent:!0,opacity:a?.85:n.room?.6:t.dark?.3:.34,side:Ht,depthWrite:!1,polygonOffset:!0,polygonOffsetFactor:-2,polygonOffsetUnits:-2}),B=new G(b,A);B.renderOrder=6,s.add(B);const H=new ct;if(H.setAttribute("position",new tt(w,3)),s.add(new Ct(H,new Pt({color:t.tealBright}))),u.length){const T=new ct;T.setAttribute("position",new tt(u,3)),s.add(new Ct(T,new Pt({color:t.teal})))}return i}const ls=`
out vec3 vWorld;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`,hs=`
precision highp float;
precision highp sampler3D;
uniform sampler3D uVol0;
uniform sampler3D uVolS;
uniform vec3 uMin;
uniform vec3 uMax;
uniform vec3 uDim;
uniform float uUseShield;
uniform float uShieldZc;
uniform float uShieldZh;
in vec3 vWorld;
out vec4 fragColor;

float fieldAt(vec3 p) {
  vec3 f = clamp((p - uMin) / (uMax - uMin), 0.0, 1.0);
  vec3 uvw = (0.5 + f * (uDim - 1.0)) / uDim;
  if (uUseShield > 0.5 && abs(p.z - uShieldZc) <= uShieldZh) return texture(uVolS, uvw).r;
  return texture(uVol0, uvw).r;
}

bool boxHit(vec3 ro, vec3 rd, out float tn, out float tf) {
  vec3 inv = 1.0 / rd;
  vec3 a = (uMin - ro) * inv;
  vec3 b = (uMax - ro) * inv;
  vec3 lo = min(a, b);
  vec3 hi = max(a, b);
  tn = max(max(lo.x, lo.y), max(lo.z, 0.0));
  tf = min(min(hi.x, hi.y), hi.z);
  return tf > tn;
}

float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
`,Gi=hs+`
uniform float uT0;
uniform float uT1;
uniform float uStrength;
uniform vec3 uColA;
uniform vec3 uColB;
void main() {
  vec3 ro = cameraPosition;
  vec3 rd = normalize(vWorld - ro);
  float tn; float tf;
  if (!boxHit(ro, rd, tn, tf)) discard;
  const int N = 64;
  float dt = (tf - tn) / float(N);
  float j = hash(gl_FragCoord.xy);
  vec3 col = vec3(0.0);
  float alpha = 0.0;
  float scale = uStrength * dt / 22.0;
  for (int i = 0; i < N; i++) {
    vec3 p = ro + rd * (tn + (float(i) + j) * dt);
    float t = clamp((fieldAt(p) - uT0) / (uT1 - uT0), 0.0, 1.0);
    float d = t * t * t * t * scale;
    vec3 c = mix(uColA, uColB, t * t);
    col += (1.0 - alpha) * d * c;
    alpha += (1.0 - alpha) * d;
    if (alpha > 0.97) break;
  }
  if (alpha < 0.004) discard;
  fragColor = vec4(col / max(alpha, 1e-4), alpha);
}`,$i=hs+`
uniform float uIso;
uniform vec3 uIsoColor;
uniform float uOpacity;
uniform vec3 uLight;
uniform mat4 uViewProj;
void main() {
  vec3 ro = cameraPosition;
  vec3 rd = normalize(vWorld - ro);
  float tn; float tf;
  if (!boxHit(ro, rd, tn, tf)) discard;
  const int N = 112;
  float dt = (tf - tn) / float(N);
  float j = hash(gl_FragCoord.xy);
  float prev = fieldAt(ro + rd * tn);
  float tPrev = tn;
  bool found = false;
  vec3 hit = vec3(0.0);
  for (int i = 1; i <= N; i++) {
    float tt = tn + (float(i) - 1.0 + j) * dt;
    float v = fieldAt(ro + rd * tt);
    if ((prev - uIso) * (v - uIso) < 0.0) {
      float f = (uIso - prev) / (v - prev);
      hit = ro + rd * mix(tPrev, tt, f);
      found = true;
      break;
    }
    prev = v; tPrev = tt;
  }
  if (!found) discard;
  vec3 e = (uMax - uMin) / uDim * 0.75;
  vec3 g = vec3(
    fieldAt(hit + vec3(e.x, 0.0, 0.0)) - fieldAt(hit - vec3(e.x, 0.0, 0.0)),
    fieldAt(hit + vec3(0.0, e.y, 0.0)) - fieldAt(hit - vec3(0.0, e.y, 0.0)),
    fieldAt(hit + vec3(0.0, 0.0, e.z)) - fieldAt(hit - vec3(0.0, 0.0, e.z))) / (2.0 * e);
  vec3 n = normalize(-g + vec3(1e-6));
  if (dot(n, rd) > 0.0) n = -n;
  float diffuse = 0.42 + 0.58 * max(dot(n, normalize(uLight)), 0.0);
  float rim = pow(1.0 - max(dot(n, -rd), 0.0), 2.5);
  vec3 c = uIsoColor * diffuse + vec3(1.0) * rim * 0.28;
  fragColor = vec4(c, clamp(uOpacity + rim * 0.35, 0.0, 0.95));
  vec4 clip = uViewProj * vec4(hit, 1.0);
  gl_FragDepth = clamp(clip.z / clip.w * 0.5 + 0.5, 0.0, 1.0);
}`;function Vi(n,t,e,s){const i=new Ys(n,t,e,s);return i.format=Zs,i.type=qs,i.minFilter=ae,i.magFilter=ae,i.wrapS=i.wrapT=i.wrapR=Xs,i.unpackAlignment=1,i.needsUpdate=!0,i}function Dt(n){return new Te().setStyle(n,Ks)}function cs(){return{uVol0:{value:null},uVolS:{value:null},uMin:{value:new k},uMax:{value:new k(1,1,1)},uDim:{value:new k(2,2,2)},uUseShield:{value:0},uShieldZc:{value:0},uShieldZh:{value:0}}}function Yi(){return new Me({glslVersion:is,vertexShader:ls,fragmentShader:Gi,uniforms:{...cs(),uT0:{value:.3},uT1:{value:.9},uStrength:{value:1},uColA:{value:Dt("#FFB454")},uColB:{value:Dt("#FFF3C4")}},side:ss,transparent:!0,depthTest:!1,depthWrite:!1})}function Zi(){return new Me({glslVersion:is,vertexShader:ls,fragmentShader:$i,uniforms:{...cs(),uIso:{value:.5},uIsoColor:{value:Dt("#6B3FA0")},uOpacity:{value:.5},uLight:{value:new k(-.4,.8,.5)},uViewProj:{value:new ts}},side:ss,transparent:!0,depthTest:!0,depthWrite:!0})}function ye(n,t,e){return n>0?Math.log10(n/t)/Math.log10(e/t):-1}const qi=.3;function _e(n,t,e,s){return e==="limit"&&t?{max:t,decades:3,basis:"limit"}:e==="log"?{max:Math.max(s??0,n*30),decades:3,basis:"log"}:{max:n>0?n:1,decades:3,basis:"peak"}}function Xe(n){const t=parseInt(n.replace("#",""),16);return[t>>16&255,t>>8&255,t&255]}class Xi{constructor(t,e,s,i){P(this,"onHover",null);P(this,"onPick",null);P(this,"host");P(this,"overlay");P(this,"renderer");P(this,"scene",new Qs);P(this,"camera");P(this,"controls");P(this,"pal");P(this,"dark");P(this,"staticGroup",new ne);P(this,"layerGroups",{});P(this,"pinGroup",new ne);P(this,"lineMats",[]);P(this,"pickables",[]);P(this,"data",null);P(this,"ground",null);P(this,"section",null);P(this,"vol",null);P(this,"volTex",{});P(this,"sectionMaxB",null);P(this,"sectionMaxE",null);P(this,"groundCanvas",document.createElement("canvas"));P(this,"groundTex");P(this,"groundMesh");P(this,"sectionCanvas",document.createElement("canvas"));P(this,"sectionTex");P(this,"sectionMesh");P(this,"sectionFrame");P(this,"glowMesh");P(this,"isoMesh");P(this,"opts");P(this,"labels",[]);P(this,"pins",[]);P(this,"raf",0);P(this,"dirty",!0);P(this,"disposed",!1);P(this,"ro");P(this,"pointer",{x:0,y:0,cx:0,cy:0,inside:!1,moved:!1,downX:0,downY:0,down:!1});P(this,"tween",null);P(this,"firstData",!0);P(this,"sun");P(this,"hemi");P(this,"onPointerMove",t=>{const e=this.renderer.domElement.getBoundingClientRect();this.pointer.x=(t.clientX-e.left)/e.width*2-1,this.pointer.y=-((t.clientY-e.top)/e.height)*2+1,this.pointer.cx=t.clientX,this.pointer.cy=t.clientY,this.pointer.inside=!0,this.pointer.moved=!0});P(this,"onPointerDown",t=>{this.pointer.down=t.button===0,this.pointer.downX=t.clientX,this.pointer.downY=t.clientY});P(this,"onPointerUp",t=>{if(!this.pointer.down||(this.pointer.down=!1,Math.hypot(t.clientX-this.pointer.downX,t.clientY-this.pointer.downY)>4))return;const e=this.probe();e&&this.onPick&&this.onPick({x:+e.x.toFixed(2),y:+e.y.toFixed(2),z:+e.z.toFixed(2),where:e.where})});P(this,"onPointerLeave",()=>{var t;this.pointer.inside=!1,(t=this.onHover)==null||t.call(this,null)});P(this,"raycaster",new hi);P(this,"loop",()=>{var t;if(!this.disposed){if(this.raf=requestAnimationFrame(this.loop),this.tween){const e=Math.min(1,(performance.now()-this.tween.t0)/this.tween.dur),s=e<.5?2*e*e:1-Math.pow(-2*e+2,2)/2;this.camera.position.lerpVectors(this.tween.p0,this.tween.p1,s),this.controls.target.lerpVectors(this.tween.q0,this.tween.q1,s),e>=1&&(this.tween=null),this.dirty=!0}this.controls.update(),this.pointer.moved&&this.pointer.inside&&!this.pointer.down&&(this.pointer.moved=!1,(t=this.onHover)==null||t.call(this,this.probe())),this.dirty&&(this.dirty=!1,this.render())}});P(this,"v",new k);this.host=t,this.overlay=e,this.opts=s,this.dark=i,this.pal=qe(i),this.renderer=new Js({antialias:!0,alpha:!0,powerPreference:"high-performance"}),this.renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2)),this.renderer.setClearColor(0,0),this.renderer.shadowMap.enabled=!0,this.renderer.shadowMap.type=ti,t.appendChild(this.renderer.domElement),this.camera=new ei(36,1,.5,8e3),this.camera.position.set(120,80,150),this.controls=new xi(this.camera,this.renderer.domElement),this.controls.enableDamping=!0,this.controls.dampingFactor=.09,this.controls.maxPolarAngle=Math.PI/2-.015,this.controls.minDistance=6,this.controls.maxDistance=3e3,this.controls.zoomToCursor=!0,this.controls.addEventListener("change",()=>{this.dirty=!0}),this.controls.addEventListener("start",()=>{this.tween=null}),this.hemi=new si(16777215,8952234,1),this.sun=new ii(16777215,1.7),this.sun.castShadow=!0,this.sun.shadow.mapSize.set(2048,2048),this.sun.shadow.bias=-4e-4,this.sun.shadow.normalBias=.6,this.scene.add(this.hemi,this.sun,this.sun.target,this.staticGroup,this.pinGroup),this.groundCanvas.width=720,this.groundCanvas.height=400,this.groundTex=new oe(this.groundCanvas),this.sectionCanvas.width=483,this.sectionCanvas.height=243,this.sectionTex=new oe(this.sectionCanvas);for(const l of[this.groundTex,this.sectionTex])l.colorSpace=Ce,l.minFilter=ae,l.magFilter=ae,l.generateMipmaps=!1;const r=()=>{const l=new ct;return l.setAttribute("position",new tt(new Float32Array(12),3)),l.setAttribute("uv",new tt([0,0,1,0,1,1,0,1],2)),l.setIndex([0,1,2,0,2,3]),l};this.groundMesh=new G(r(),new ft({map:this.groundTex,transparent:!0,depthWrite:!1,side:Ht})),this.groundMesh.renderOrder=2,this.sectionMesh=new G(r(),new ft({map:this.sectionTex,transparent:!0,depthWrite:!1,side:Ht})),this.sectionMesh.renderOrder=4;const o=new ct;o.setAttribute("position",new tt(new Float32Array(12),3)),this.sectionFrame=new ni(o,new Pt({color:this.pal.ink,transparent:!0,opacity:.55})),this.sectionFrame.renderOrder=5,this.glowMesh=new G(new zt(1,1,1),Yi()),this.glowMesh.renderOrder=8,this.glowMesh.frustumCulled=!1,this.isoMesh=new G(new zt(1,1,1),Zi()),this.isoMesh.renderOrder=7,this.isoMesh.frustumCulled=!1,this.glowMesh.visible=this.isoMesh.visible=!1,this.scene.add(this.groundMesh,this.sectionMesh,this.sectionFrame,this.isoMesh,this.glowMesh);const a=this.renderer.domElement;a.addEventListener("pointermove",this.onPointerMove),a.addEventListener("pointerdown",this.onPointerDown),a.addEventListener("pointerup",this.onPointerUp),a.addEventListener("pointerleave",this.onPointerLeave),this.ro=new ResizeObserver(()=>this.resize()),this.ro.observe(t),this.resize(),this.loop()}setData(t){const e=!this.data||this.data.span!==t.span||this.data.x0!==t.x0||this.data.x1!==t.x1;this.data=t,this.ground={nx:t.ground.nx,ny:t.ground.nz,B0:pt(t.ground.B0),BS:pt(t.ground.BS),E0:pt(t.ground.E0),ES:pt(t.ground.ES)},this.rebuildStatic(),this.placeFieldSurfaces(),this.paintGround(),this.applyVolume(),this.applyLayers(),this.firstData?(this.firstData=!1,this.setView("iso",!1)):e&&this.setView("iso",!0),this.dirty=!0}setSection(t){this.section={nx:t.nx,ny:t.ny,B0:pt(t.B0),BS:pt(t.BS),E0:pt(t.E0),ES:pt(t.ES),z:t.z,x0:t.x0,x1:t.x1,y0:t.y0,y1:t.y1,shield:t.shield_here},this.sectionMaxB=qt(this.section.B0),this.sectionMaxE=qt(this.section.E0),this.placeFieldSurfaces(),this.paintSection(),this.opts.scale==="log"&&this.paintGround(),this.applyLayers(),this.dirty=!0}setVolume(t){var e;for(const s of Object.keys(this.volTex))(e=this.volTex[s])==null||e.dispose();if(this.volTex={},this.vol=t,t)for(const s of["B0","BS","E0","ES"])this.volTex[s]=Vi(Ts(t[s]),t.nx,t.ny,t.nz);this.applyVolume(),this.applyLayers(),this.dirty=!0}setOptions(t){const e=this.opts;this.opts=t,(e.quantity!==t.quantity||e.view!==t.view||e.scale!==t.scale||e.isoLevel!==t.isoLevel||e.layers.contours!==t.layers.contours)&&(this.paintGround(),this.paintSection(),this.refreshBuildingLabels()),e.sectionZ!==t.sectionZ&&this.placeFieldSurfaces(),this.applyVolume(),this.applyLayers(),this.dirty=!0}setPins(t){this.pins=t,this.rebuildPins(),this.dirty=!0}setTheme(t){t!==this.dark&&(this.dark=t,this.pal=qe(t),this.sectionFrame.material.color.set(this.pal.ink),this.data&&(this.rebuildStatic(),this.paintGround(),this.paintSection(),this.applyVolume(),this.applyLayers(),this.rebuildPins()),this.dirty=!0)}getSectionMax(t){return t==="B"?this.sectionMaxB:this.sectionMaxE}getGroundPeak(t){return this.ground?qt(t==="B"?this.ground.B0:this.ground.E0):0}clearStatic(){this.staticGroup.traverse(t=>{var i,r,o,a;const e=t;(r=(i=e.geometry)==null?void 0:i.dispose)==null||r.call(i);const s=Array.isArray(e.material)?e.material:e.material?[e.material]:[];for(const l of s)(a=(o=l.map)==null?void 0:o.dispose)==null||a.call(o),l.dispose()}),this.staticGroup.clear(),this.lineMats=[],this.pickables=[],this.layerGroups={};for(const t of this.labels.filter(e=>e.group!=="pin"))t.el.remove();this.labels=this.labels.filter(t=>t.group==="pin")}fat(t,e,s,i=1){if(!t.length)return null;const r=new rs;r.setPositions(t);const o=new as({color:new Te(e).getHex(),linewidth:s,transparent:i<1,opacity:i,depthWrite:i>=1});o.resolution.set(this.host.clientWidth||800,this.host.clientHeight||600),this.lineMats.push(o);const a=new Li(r,o);return a.frustumCulled=!1,a}addTo(t,...e){var s;for(const i of e)i&&(this.staticGroup.add(i),((s=this.layerGroups)[t]??(s[t]=[])).push(i))}rebuildStatic(){const t=this.data,e=this.pal;this.clearStatic();const s=t.span,i=s*qi,r=Math.max(s+i,t.x1-t.x0,90);this.hemi.color.set(e.dark?"#8FA6C4":"#FFFFFF"),this.hemi.groundColor.set(e.dark?"#0B131D":"#C9D3DA"),this.hemi.intensity=e.dark?.9:1.15,this.sun.intensity=e.dark?1.1:1.75,this.sun.position.set(-r*.55,r*1.1,r*.75),this.sun.target.position.set(0,0,0);const o=this.sun.shadow.camera;o.left=-r*1.2,o.right=r*1.2,o.top=r*1.2,o.bottom=-r*1.2,o.near=1,o.far=r*4,o.updateProjectionMatrix();const a=new G(new oi(r*5,72),new mt({color:e.ground}));a.rotation.x=-Math.PI/2,a.receiveShadow=!0,this.staticGroup.add(a);const l=Math.ceil(r*2.4/100)*100,h=new Re(l,l/10,e.grid,e.grid);h.position.y=.02;const w=new Re(l,l/50,e.gridMajor,e.gridMajor);w.position.y=.03;for(const v of[h,w])v.material.transparent=!0,v.material.opacity=e.dark?.8:.75,v.material.depthWrite=!1;this.staticGroup.add(h,w),this.scene.fog=new ai(e.dark?"#111C2B":"#EEF3F6",r*3.2,r*9);const u=new ri(2*t.row,2*(s+i)),x=new G(u,new ft({color:e.row,transparent:!0,opacity:e.dark?.1:.07,depthWrite:!1}));x.rotation.x=-Math.PI/2,x.position.y=.05,x.renderOrder=1;const _=[];for(const v of[-1,1])_.push(v*t.row,.08,-(s+i),v*t.row,.08,s+i);const C=new ct;C.setAttribute("position",new tt(_,3));const p=new Ct(C,new li({color:e.row,dashSize:4,gapSize:3,transparent:!0,opacity:.75}));p.computeLineDistances(),this.addTo("row",x,p);const d={lattice:[],arms:[],insul:[],meshes:[]},g=["A","B","C","off"],S={A:[],B:[],C:[],off:[]},f={A:[],B:[],C:[],off:[]};for(const v of t.lines){for(const b of[-s,s])Fi(v,b,d,e);const E=Oi(v,s,i);for(const b of g)S[b].push(...E.main[b]),f[b].push(...E.stub[b])}this.addTo("lines",this.fat(d.lattice,e.steel,1.25),this.fat(d.arms,e.pole,3.2),this.fat(d.insul,e.insulator,3.4),...d.meshes);const y=v=>v==="off"?e.dark?"#7C8896":"#9AA3AA":e.phase[v];for(const v of g)this.addTo("lines",this.fat(S[v],y(v),v==="off"?1.6:2.3),this.fat(f[v],y(v),v==="off"?1.2:1.6,.38));t.buildings.forEach((v,E)=>{const b=Ui(v,e,E);t.shield.on&&t.shield.room&&E===t.shield.target_building&&b.traverse(B=>{const H=B;if(H.isMesh)for(const T of Array.isArray(H.material)?H.material:H.material?[H.material]:[])T.transparent=!0,T.opacity=.2,T.depthWrite=!1}),this.addTo("buildings",b),b.traverse(B=>{B.isMesh&&(B.userData.building=E,this.pickables.push(B))});const A=new G(new Ne(.55,16,12),new ft({color:e.dark?"#4DA3FF":"#0072B5",depthTest:!1}));A.position.set(v.probe[0],v.probe[1],v.probe[2]),A.renderOrder=9,this.addTo("buildings",A)});const M=Wi(t.shield,e,s+i);this.addTo("shield",M.group,this.fat(M.wires,e.tealBright,2.6),this.fat(M.bonds,e.teal,2)),this.buildLabels()}buildLabels(){const t=this.data;for(const s of t.lines){const i=be(s),r=s.circuits.filter(l=>l.on),o=[...new Set(r.map(l=>l.kv.toFixed(0)))],a=s.circuits.length>1&&(s.separate||o.length>1||r.length<s.circuits.length)?`${o.join("/")||"—"} kV · ${r.length} of ${s.circuits.length} circuits live`:`${s.kv.toFixed(0)} kV · ${s.operating_a.toFixed(0)} A${s.circuits.length>1?" per circuit":""}`;this.makeLabel(`<b>${te(s.name)}</b><span>${a}</span>`,"line",new k(s.xc,i.top+2,-t.span),"static")}if(t.buildings.forEach((s,i)=>this.makeLabel("","bldg",new k(s.x0+s.w/2,s.h+3.5,s.z),`b${i}`)),this.refreshBuildingLabels(),t.shield.on&&t.shield.walls.length){let s=0,i=0;for(const o of t.shield.walls)s+=(o[0]+o[2])/2,i=Math.max(i,o[1],o[3]);t.shield.attached&&(i=-1.5);const r=t.shield.is_wire?`<b>${t.shield.preset==="passive-loop"?"Passive loop":"Screening wires"}</b><span>${t.shield.wires.length} × ${t.shield.wire_mm2} mm²${t.shield.loop_current_a?` · ${t.shield.loop_current_a.toFixed(0)} A`:""}</span>`:`<b>${te(t.shield.material.label.split(" (")[0])}${t.shield.layer2?` + ${te(t.shield.layer2.split(" (")[0])}`:""}</b><span>${t.shield.thickness_mm.toFixed(t.shield.thickness_mm<10?1:0)} mm${t.shield.grounded?" · earthed":" · floating"}</span>`;this.makeLabel(r,"shield",new k(s/t.shield.walls.length,i+1.5,Math.min(t.span,t.shield.zc+t.shield.zh)),"static")}const e=t.x1-t.x0>220?50:t.x1-t.x0>110?20:10;for(let s=Math.ceil(t.x0/e)*e;s<=t.x1+1e-6;s+=e)this.makeLabel(s===0?"0 m":`${s>0?"+":"−"}${Math.abs(s)}`,"tick",new k(s,0,t.span+4),"static");this.makeLabel(`ROW ±${t.row} m`,"tick",new k(t.row,0,-t.span-5),"static")}refreshBuildingLabels(){const t=this.data;if(!t)return;const e=this.opts.quantity,s=e==="B"?"µT":"kV/m";t.buildings.forEach((i,r)=>{const o=this.labels.find(_=>_.group===`b${r}`);if(!o)return;let a=e==="B"?i.b_in0??i.b0:i.e_in0??i.e0,l=e==="B"?i.b_inS??i.bS:i.e_inS??i.eS,h="inside ";const w=t.shield.on&&r===t.shield.target_building?t.shield.protected:null;if(w&&t.shield.room){const _=e==="B"?w.b:w.e;a=_.avg0,l=_.avgS,h="room "}const u=t.shield.on&&Math.abs(l-a)>1e-4*Math.max(a,1e-9),x=u&&l<a*.001;o.el.innerHTML=`<b>${te(i.name)}</b><span>${h}${u?`${St(a)} → <i>${x?"≈ 0":St(l)}</i>`:St(a)} ${s}</span>`})}makeLabel(t,e,s,i){const r=document.createElement("div");r.className=`twin-label ${e}`,r.innerHTML=t,this.overlay.appendChild(r);const o={el:r,pos:s,group:i};return this.labels.push(o),o}rebuildPins(){this.pinGroup.traverse(i=>{var o,a,l,h;const r=i;(a=(o=r.geometry)==null?void 0:o.dispose)==null||a.call(o),(h=(l=r.material)==null?void 0:l.dispose)==null||h.call(l)}),this.pinGroup.clear();for(const i of this.labels.filter(r=>r.group==="pin"))i.el.remove();this.labels=this.labels.filter(i=>i.group!=="pin");const t=this.pal,e=[],s=this.opts.quantity;for(const i of this.pins){const r=new G(new Ne(.75,18,14),new ft({color:t.violet,depthTest:!1}));r.position.set(i.x,i.y,i.z),r.renderOrder=10,this.pinGroup.add(r),e.push(i.x,0,i.z,i.x,i.y,i.z);const o=s==="B"?i.b0:i.e0,a=s==="B"?i.bS:i.eS,l=Math.abs(a-o)>1e-4*Math.max(o,1e-9);this.makeLabel(`<em>${i.n}</em><span>${l?`${St(o)} → <i>${St(a)}</i>`:St(o)} ${s==="B"?"µT":"kV/m"}</span>`,"pin",new k(i.x,i.y+1.4,i.z),"pin")}if(e.length){const i=new ct;i.setAttribute("position",new tt(e,3)),this.pinGroup.add(new Ct(i,new Pt({color:t.violet,transparent:!0,opacity:.7})))}this.applyLayers()}placeFieldSurfaces(){var a,l;const t=this.data;if(!t)return;const e=this.groundMesh.geometry.getAttribute("position"),s=.12;e.setXYZ(0,t.x0,s,-t.span),e.setXYZ(1,t.x1,s,-t.span),e.setXYZ(2,t.x1,s,t.span),e.setXYZ(3,t.x0,s,t.span),e.needsUpdate=!0,this.groundMesh.geometry.computeBoundingSphere();const i=Math.max(-t.span,Math.min(t.span,this.opts.sectionZ)),r=((a=this.section)==null?void 0:a.y0)??.3,o=((l=this.section)==null?void 0:l.y1)??t.y_top;for(const h of[this.sectionMesh.geometry,this.sectionFrame.geometry]){const w=h.getAttribute("position");w.setXYZ(0,t.x0,r,i),w.setXYZ(1,t.x1,r,i),w.setXYZ(2,t.x1,o,i),w.setXYZ(3,t.x0,o,i),w.needsUpdate=!0,h.computeBoundingSphere()}}contours(t,e){if(!this.opts.layers.contours||this.opts.view==="diff")return[];const s=this.pal,i=wi(t/200,t,5).map(r=>({level:r,color:s.dark?[230,237,244]:[15,27,36],alpha:.42}));return e&&i.push({level:e,color:Xe(s.red),bold:!0}),this.opts.isoLevel>0&&i.push({level:this.opts.isoLevel,color:Xe(s.violet),bold:!0}),i}paintGround(){const t=this.data,e=this.ground;if(!t||!e)return;const s=this.opts.quantity,i=s==="B"?e.B0:e.E0,r=s==="B"?e.BS:e.ES,o=s==="B"?t.limits.b:t.limits.e,a=_e(qt(i),o,this.opts.scale,this.getSectionMax(s)),l=this.groundCanvas.height,h=new Uint8Array(l);if(t.shield.on)for(let w=0;w<l;w++){const u=-t.span+2*t.span*(l-1-w)/(l-1);h[w]=Math.abs(u-t.shield.zc)<=t.shield.zh+1e-6?1:0}Ie(this.groundCanvas,{nx:e.nx,ny:e.ny,a0:i,aS:r},{view:this.opts.view,mode:this.opts.scale,max:a.max,logDecades:a.decades,dark:this.dark,alphaLo:0,alphaHi:.9,contours:this.contours(a.max,o),rowMask:h}),this.groundTex.needsUpdate=!0}paintSection(){const t=this.data,e=this.section;if(!t||!e)return;const s=this.opts.quantity,i=s==="B"?e.B0:e.E0,r=s==="B"?e.BS:e.ES,o=s==="B"?t.limits.b:t.limits.e,a=_e(this.getGroundPeak(s),o,this.opts.scale,this.getSectionMax(s));Ie(this.sectionCanvas,{nx:e.nx,ny:e.ny,a0:i,aS:r},{view:this.opts.view,mode:this.opts.scale,max:a.max,logDecades:a.decades,dark:this.dark,alphaLo:.05,alphaHi:.8,contours:this.contours(a.max,o),shieldAll:!0}),this.sectionTex.needsUpdate=!0}applyVolume(){const t=this.data,e=this.vol;if(!t||!e)return;const s=this.opts.quantity,i=s==="B"?e.b_lo:e.e_lo,r=s==="B"?e.b_hi:e.e_hi,o=this.opts.view!=="without"&&t.shield.on?1:0,a=this.getGroundPeak(s)||r/100;for(const w of[this.glowMesh,this.isoMesh]){w.scale.set(e.x1-e.x0,e.y1-e.y0,e.z1-e.z0),w.position.set((e.x0+e.x1)/2,(e.y0+e.y1)/2,(e.z0+e.z1)/2);const u=w.material.uniforms;u.uVol0.value=this.volTex[s==="B"?"B0":"E0"]??null,u.uVolS.value=this.volTex[s==="B"?"BS":"ES"]??null,u.uMin.value.set(e.x0,e.y0,e.z0),u.uMax.value.set(e.x1,e.y1,e.z1),u.uDim.value.set(e.nx,e.ny,e.nz),u.uUseShield.value=o,u.uShieldZc.value=t.shield.zc,u.uShieldZh.value=t.shield.zh}const l=this.glowMesh.material.uniforms;l.uT0.value=Math.max(0,ye(a*1.4,i,r)),l.uT1.value=Math.min(1,Math.max(l.uT0.value+.08,ye(Math.min(r,a*90),i,r))),l.uStrength.value=.2+2.2*this.opts.glow,l.uColA.value.copy(Dt(this.dark?"#FFB454":"#F29A2E")),l.uColB.value.copy(Dt(this.dark?"#FFF6D6":"#C53A1B"));const h=this.isoMesh.material.uniforms;h.uIso.value=ye(this.opts.isoLevel,i,r),h.uIsoColor.value.copy(Dt(this.pal.violet)),h.uOpacity.value=this.dark?.42:.46}applyLayers(){const t=this.opts.layers;for(const s of Object.keys(this.layerGroups))for(const i of this.layerGroups[s]??[])i.visible=t[s];this.groundMesh.visible=t.ground&&!!this.ground,this.sectionMesh.visible=this.sectionFrame.visible=t.section&&!!this.section;const e=this.isoMesh.material.uniforms.uIso.value;this.glowMesh.visible=t.glow&&!!this.vol&&!!this.volTex.B0,this.isoMesh.visible=t.iso&&!!this.vol&&!!this.volTex.B0&&e>0&&e<1;for(const s of this.labels)s.el.style.visibility=t.labels||s.group==="pin"?"":"hidden"}setView(t,e=!0){const s=this.data;if(!s)return;const i=Math.max(s.span*1.7,(s.x1-s.x0)*1.3,120),r=(s.x0+s.x1)/2,o=Math.max(20,...s.lines.map(h=>be(h).top));let a,l;if(t==="front"?(a=new k(r,o*.62,Math.max(s.span*.62,(s.x1-s.x0)*.9)),l=new k(r,o*.4,0)):t==="side"?(a=new k(s.x1+i*1.15,o*1.1,.01),l=new k(0,o*.35,0)):t==="top"?(a=new k(r,i*2.25,.5),l=new k(r,0,0)):(a=new k(r+i*1.22,i*.56,i*.56),l=new k(r-i*.04,o*.2,0)),!e){this.camera.position.copy(a),this.controls.target.copy(l),this.controls.update(),this.dirty=!0;return}this.tween={t0:performance.now(),dur:650,p0:this.camera.position.clone(),p1:a,q0:this.controls.target.clone(),q1:l}}resize(){const t=this.host.clientWidth,e=this.host.clientHeight;if(!(!t||!e)){this.renderer.setSize(t,e,!1),this.camera.aspect=t/e,this.camera.updateProjectionMatrix();for(const s of this.lineMats)s.resolution.set(t,e);this.dirty=!0}}probe(){const t=this.data,e=this.ground;if(!t||!e)return null;this.raycaster.setFromCamera(new J(this.pointer.x,this.pointer.y),this.camera);const s=this.raycaster.ray;let i=null;const r=(h,w)=>{(!i||h<i.dist)&&(i={dist:h,info:w})};if(this.opts.layers.buildings&&this.pickables.length){const h=this.raycaster.intersectObjects(this.pickables,!1)[0];h&&r(h.distance,{x:h.point.x,y:Math.max(0,h.point.y),z:h.point.z,where:"building",b0:null,bS:null,e0:null,eS:null,shielded:!1})}const o=this.section,a=Math.max(-t.span,Math.min(t.span,this.opts.sectionZ));if(this.opts.layers.section&&o&&Math.abs(s.direction.z)>1e-6){const h=(a-s.origin.z)/s.direction.z;if(h>0){const w=s.origin.x+s.direction.x*h,u=s.origin.y+s.direction.y*h;if(w>=o.x0&&w<=o.x1&&u>=o.y0&&u<=o.y1){const x=Math.abs(o.z-a)<.26,_=(w-o.x0)/(o.x1-o.x0)*(o.nx-1),C=(u-o.y0)/(o.y1-o.y0)*(o.ny-1);r(h,x?{x:w,y:u,z:a,where:"section",b0:rt(o.B0,o.nx,o.ny,_,C),bS:rt(o.BS,o.nx,o.ny,_,C),e0:rt(o.E0,o.nx,o.ny,_,C),eS:rt(o.ES,o.nx,o.ny,_,C),shielded:o.shield}:{x:w,y:u,z:a,where:"section",b0:null,bS:null,e0:null,eS:null,shielded:!1})}}}if(s.direction.y<-1e-6){const h=-s.origin.y/s.direction.y,w=s.origin.x+s.direction.x*h,u=s.origin.z+s.direction.z*h;if(h>0&&w>=t.x0&&w<=t.x1&&u>=-t.span&&u<=t.span){const x=(w-t.x0)/(t.x1-t.x0)*(e.nx-1),_=(u+t.span)/(2*t.span)*(e.ny-1),C=t.shield.on&&Math.abs(u-t.shield.zc)<=t.shield.zh,p=rt(e.B0,e.nx,e.ny,x,_),d=rt(e.E0,e.nx,e.ny,x,_);r(h,{x:w,y:t.meas_height,z:u,where:"ground",b0:p,bS:C?rt(e.BS,e.nx,e.ny,x,_):p,e0:d,eS:C?rt(e.ES,e.nx,e.ny,x,_):d,shielded:C})}}const l=i;return l?{...l.info,clientX:this.pointer.cx,clientY:this.pointer.cy}:null}render(){if(this.isoMesh.visible){const t=this.isoMesh.material.uniforms;this.camera.updateMatrixWorld(),t.uViewProj.value.multiplyMatrices(this.camera.projectionMatrix,this.camera.matrixWorldInverse),t.uLight.value.copy(this.sun.position).normalize()}this.renderer.render(this.scene,this.camera),this.layoutLabels()}layoutLabels(){const t=this.host.clientWidth,e=this.host.clientHeight;for(const s of this.labels){this.v.copy(s.pos).project(this.camera);const i=this.v.z>-1&&this.v.z<1&&Math.abs(this.v.x)<1.1&&Math.abs(this.v.y)<1.1;s.el.style.display=i?"":"none",i&&(s.el.style.transform=`translate(-50%, -100%) translate(${((this.v.x*.5+.5)*t).toFixed(1)}px, ${((-this.v.y*.5+.5)*e).toFixed(1)}px)`)}}capture(){this.render();const t=this.renderer.domElement,e=document.createElement("canvas");e.width=t.width,e.height=t.height;const s=e.getContext("2d"),i=s.createLinearGradient(0,0,0,e.height);if(this.dark?(i.addColorStop(0,"#070D16"),i.addColorStop(.55,"#0F1B2C"),i.addColorStop(1,"#17263B")):(i.addColorStop(0,"#CFE0EE"),i.addColorStop(.45,"#E9F1F7"),i.addColorStop(1,"#F4F7F9")),s.fillStyle=i,s.fillRect(0,0,e.width,e.height),s.drawImage(t,0,0),this.opts.layers.labels){const r=e.width/(this.host.clientWidth||e.width);s.textAlign="center";for(const o of this.labels){if(o.el.style.display==="none")continue;this.v.copy(o.pos).project(this.camera);const a=(this.v.x*.5+.5)*e.width,l=(-this.v.y*.5+.5)*e.height,h=(o.el.textContent||"").trim();if(!h)continue;s.font=`${o.group==="static"&&o.el.classList.contains("tick")?500:600} ${Math.round(11*r)}px Segoe UI, Helvetica, Arial, sans-serif`;const w=s.measureText(h).width,u=5*r,x=17*r;o.el.classList.contains("tick")||(s.fillStyle=this.dark?"rgba(15,24,35,0.88)":"rgba(255,255,255,0.9)",s.strokeStyle=this.dark?"#33455A":"#C5CCD2",s.lineWidth=r,s.beginPath(),s.rect(a-w/2-u,l-x-2*r,w+2*u,x),s.fill(),s.stroke()),s.fillStyle=this.dark?"#E6EDF4":"#0F1B24",s.fillText(h,a,l-7*r)}}return e.toDataURL("image/png")}dispose(){var e;this.disposed=!0,cancelAnimationFrame(this.raf),this.ro.disconnect();const t=this.renderer.domElement;t.removeEventListener("pointermove",this.onPointerMove),t.removeEventListener("pointerdown",this.onPointerDown),t.removeEventListener("pointerup",this.onPointerUp),t.removeEventListener("pointerleave",this.onPointerLeave),this.controls.dispose(),this.clearStatic();for(const s of this.labels)s.el.remove();this.labels=[];for(const s of Object.keys(this.volTex))(e=this.volTex[s])==null||e.dispose();this.groundTex.dispose(),this.sectionTex.dispose();for(const s of[this.groundMesh,this.sectionMesh,this.glowMesh,this.isoMesh])s.geometry.dispose(),s.material.dispose();this.renderer.dispose(),t.remove()}}function te(n){return n.replace(/[&<>"']/g,t=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[t])}function St(n){if(!Number.isFinite(n))return"—";const t=Math.abs(n);return t===0?"0":t>=100?n.toFixed(0):t>=10?n.toFixed(1):t>=1?n.toFixed(2):t>=.01?n.toFixed(3):t>=.001?n.toFixed(4):n.toExponential(1)}const xe=[["ground","Ground map","Field at the measurement height, drawn on the ground along the whole span"],["section","Section","Field in a vertical plane across the corridor; move it with the slider"],["contours","Contours","Iso-lines on the maps: the limit (red), your iso level (violet) and round values"],["glow","Field glow","Volume rendering of the field around the conductors"],["iso","Iso-surface","3-D surface where the field equals the iso level"],["lines","Lines","Towers, insulators and conductors"],["buildings","Buildings","Buildings and their receptor points"],["shield","Shield","The shielding structure"],["row","ROW","Right-of-way band"],["labels","Labels","Names and values in the scene"]],Ki={ground:!0,section:!0,contours:!0,glow:!1,iso:!1,lines:!0,buildings:!0,shield:!0,row:!0,labels:!0};function Qi(){try{return JSON.parse(localStorage.getItem("taki.twin")||"{}")}catch{return{}}}function nn(){var De,ze,Ae;const n=nt(m=>m.config),t=nt(m=>m.sol),e=nt(m=>m.theme),s=nt(m=>m.setConfig),i=nt(m=>m.setPins),r=nt(m=>m.setTwinShot),o=nt(m=>m.twinShot),a=nt(m=>m.toast),l=R.useMemo(Qi,[]),[h,w]=R.useState("B"),[u,x]=R.useState("with"),[_,C]=R.useState(l.scale??"peak"),[p,d]=R.useState({...Ki,...l.layers??{}}),[g,S]=R.useState(null),[f,y]=R.useState(l.glow??.5),[M,v]=R.useState(1),[E,b]=R.useState(null),[A,B]=R.useState(!0),[H,T]=R.useState(()=>window.innerHeight>860),[,L]=R.useState(0),F=R.useRef(null),z=R.useRef(null),N=R.useRef(null),U=R.useRef(null),W=R.useRef(null),dt=Zt("/twin",{},{delay:160}),D=dt.data,ut=g??(D==null?void 0:D.zc_default)??0,ds=Cs(ut,110),At=Zt("/twin/section",{z:+ds.toFixed(1)},{enabled:p.section,delay:40}),vt=Zt("/twin/volume",{},{enabled:p.glow||p.iso,delay:200}),re=Zt("/points",{},{withPoints:!0,delay:120}),gt=!!(D!=null&&D.shield.on),st=gt?u:"without",le=h==="B"?n.twin.iso_level_uT:M,Gt=R.useMemo(()=>({quantity:h,view:st,scale:_,layers:p,sectionZ:ut,isoLevel:le,glow:f}),[h,st,_,p,ut,le,f]),he=R.useRef(Gt);he.current=Gt,R.useEffect(()=>{try{localStorage.setItem("taki.twin",JSON.stringify({layers:p,scale:_,glow:f}))}catch{}},[p,_,f]),R.useEffect(()=>{if(!F.current||!z.current)return;let m;try{m=new Xi(F.current,z.current,he.current,nt.getState().theme==="dark")}catch(j){b((j==null?void 0:j.message)||"WebGL is not available in this browser.");return}return W.current=m,m.onPick=j=>{var it;const X=nt.getState(),K=((it=X.config)==null?void 0:it.points)??[];X.setPins([...K,{x:j.x,y:j.y,z:j.z,label:j.where==="building"?"on building":""}])},m.onHover=j=>us(j),()=>{m.dispose(),W.current=null}},[]),R.useEffect(()=>{D&&W.current&&(W.current.setData(D),L(m=>m+1))},[D]),R.useEffect(()=>{At.data&&W.current&&D&&At.data.hash===D.hash&&(W.current.setSection(At.data),L(m=>m+1))},[At.data,D]),R.useEffect(()=>{W.current&&W.current.setVolume(vt.data&&D&&vt.data.hash===D.hash?vt.data:null)},[vt.data,D]),R.useEffect(()=>{var m;(m=W.current)==null||m.setOptions(Gt)},[Gt]),R.useEffect(()=>{var m,j;(j=W.current)==null||j.setPins(((m=re.data)==null?void 0:m.rows)??[])},[re.data,h]),R.useEffect(()=>{var m;(m=W.current)==null||m.setTheme(e==="dark")},[e]);const us=m=>{const j=U.current,X=N.current;if(!j||!X)return;if(!m){j.style.display="none";return}const K=X.getBoundingClientRect(),it=he.current,gs=it.quantity==="B"?"µT":"kV/m",wt=it.quantity==="B"?m.b0:m.e0,Bt=it.quantity==="B"?m.bS:m.eS,je=it.quantity==="B"?m.e0:m.b0,ws=it.quantity==="B"?"kV/m":"µT";let Ft=`<div style="color:var(--steel)">x ${m.x.toFixed(1)} · y ${m.y.toFixed(1)} · z ${m.z.toFixed(1)} m</div>`;wt!==null&&Bt!==null?(Ft+=`<div><b>${it.quantity} ${yt(wt)} ${gs}</b>${m.shielded&&Math.abs(Bt-wt)>1e-4*wt?` → <span style="color:var(--teal)">${yt(Bt)}</span> <span style="color:var(--steel)">(${Bt<=wt?"−":"+"}${Math.abs(100*(1-Bt/wt)).toFixed(0)}%)</span>`:""}</div>`,je!==null&&(Ft+=`<div style="color:var(--steel)">${it.quantity==="B"?"E":"B"} ${yt(je)} ${ws}</div>`)):Ft+=`<div style="color:var(--steel)">${m.where==="building"?"on the building":"section updating…"}</div>`,Ft+=`<div style="color:var(--steel);font-family:var(--font-ui)">click to pin${wt===null?" and read the exact value":""}</div>`,j.innerHTML=Ft,j.style.display="block";const Ot=j.offsetWidth||220,Rt=j.offsetHeight||80,Nt=m.clientX-K.left,Ut=m.clientY-K.top,ys=[[Nt+14,Ut+14],[Nt-Ot-14,Ut+14],[Nt+14,Ut-Rt-14],[Nt-Ot-14,Ut-Rt-14]],xs=[...X.querySelectorAll(".twin-legend, .twin-info")].map(_t=>_t.getBoundingClientRect()),vs=([_t,Vt])=>_t>=4&&Vt>=4&&_t+Ot<=K.width-4&&Vt+Rt<=K.height-4&&!xs.some(Yt=>_t+K.left<Yt.right&&_t+K.left+Ot>Yt.left&&Vt+K.top<Yt.bottom&&Vt+K.top+Rt>Yt.top),[bs,_s]=ys.find(vs)??[Math.max(4,Math.min(Nt+14,K.width-Ot-4)),Math.max(4,Math.min(Ut+14,K.height-Rt-4))];j.style.left=`${bs}px`,j.style.top=`${_s}px`},ps=()=>{if(W.current)try{r(W.current.capture()),a("Captured this view. It will be included in the report.")}catch{a("Could not capture the view.","error")}},fs=()=>{var j;const m=N.current;m&&(document.fullscreenElement?document.exitFullscreen():(j=m.requestFullscreen)==null||j.call(m))},jt=m=>{var j;return(j=W.current)==null?void 0:j.setView(m)},ms=m=>d(j=>({...j,[m]:!j[m]})),ce=h==="B"?"µT":"kV/m",q=D?h==="B"?D.limits.b:D.limits.e:null,bt=((De=W.current)==null?void 0:De.getGroundPeak(h))||(D?h==="B"?D.peak_b:D.peak_e:0),$t=_e(bt,q,_,((ze=W.current)==null?void 0:ze.getSectionMax(h))??null),kt=(D==null?void 0:D.span)??150,Lt=((Ae=re.data)==null?void 0:Ae.rows)??[];return E?c.jsx("div",{className:"page flush",children:c.jsx("div",{className:"twin-fallback",children:c.jsxs("div",{children:[c.jsx("h3",{children:"The 3-D view could not start"}),c.jsx("p",{className:"small mt-8",children:E}),c.jsx("p",{className:"small",children:"Every result is still available on the Field map, Lateral profile and Measure points pages. The 3-D twin needs WebGL 2, which most browsers have switched on by default."})]})})}):c.jsx("div",{className:"page flush",children:c.jsxs("div",{className:"twin",children:[c.jsxs("div",{className:"twin-bar",children:[c.jsxs("div",{className:"grp",children:[c.jsx("span",{className:"lbl",children:"Field"}),c.jsx(de,{size:"sm",value:h,onChange:w,options:[{value:"B",label:"Magnetic B"},{value:"E",label:"Electric E"}]})]}),c.jsxs("div",{className:"grp",title:"What the colours on the ground and on the section stand for",children:[c.jsx("span",{className:"lbl",children:"Colours show"}),c.jsx(de,{size:"sm",value:st,onChange:x,options:[{value:"without",label:"Field, no shield",title:"The field as it is without any shield"},{value:"with",label:"Field, with shield",disabled:!gt,title:gt?"The field with the shield in place":"Switch a shield on in the inputs first"},{value:"diff",label:"What the shield changes",disabled:!gt,title:"Not a field value: where the shield lowers the field (teal) and where it raises it (red), in percent"}]})]}),c.jsxs("div",{className:"grp",children:[c.jsx("span",{className:"lbl",children:"Scale"}),c.jsx(de,{size:"sm",value:_,onChange:C,options:[{value:"peak",label:"Peak",title:"Colours span 0 to the ground-level peak"},{value:"limit",label:"Limit",disabled:!q,title:q?"Colours span 0 to the tightest selected limit":"No limit selected for this field"},{value:"log",label:"Log",title:"Three decades, logarithmic"}]})]}),c.jsxs("div",{className:"grp",children:[c.jsx("span",{className:"lbl",children:"View"}),c.jsxs("div",{className:"seg sm",children:[c.jsx("button",{onClick:()=>jt("iso"),children:"3-D"}),c.jsx("button",{onClick:()=>jt("front"),title:"Looking along the line",children:"Front"}),c.jsx("button",{onClick:()=>jt("side"),title:"Looking across the line",children:"Side"}),c.jsx("button",{onClick:()=>jt("top"),title:"Plan view",children:"Top"})]}),c.jsx(ht,{size:"sm",variant:"ghost",icon:!0,onClick:()=>jt("iso"),title:"Reset the camera","aria-label":"Reset the camera",children:c.jsx(Ps,{size:14})})]}),c.jsx(Ds,{align:"left",button:(m,j)=>c.jsxs(ht,{size:"sm",onClick:j,title:"Choose what is drawn",children:[c.jsx(As,{size:13}),"Layers · ",xe.filter(([X])=>p[X]).length,"/",xe.length,c.jsx(Ue,{size:12})]}),children:()=>c.jsxs(c.Fragment,{children:[c.jsxs("div",{className:"head",children:[c.jsx("b",{children:"What is drawn"}),"Tick to show, untick to hide."]}),xe.map(([m,j,X])=>c.jsxs("button",{onClick:()=>ms(m),role:"menuitemcheckbox","aria-checked":p[m],style:{alignItems:"flex-start"},children:[c.jsx("span",{style:{width:14,flex:"none",marginTop:2},children:p[m]&&c.jsx(zs,{size:13})}),c.jsxs("span",{children:[j,c.jsx("span",{className:"tiny muted",style:{display:"block",maxWidth:250,whiteSpace:"normal"},children:X})]})]},m))]})}),c.jsx("span",{className:"grow"}),c.jsxs(ht,{size:"sm",onClick:ps,title:"Save this view for the report",children:[c.jsx(js,{size:13}),o?"Re-capture":"Capture for report"]}),c.jsx(ht,{size:"sm",variant:"ghost",icon:!0,onClick:fs,title:"Full screen","aria-label":"Full screen",children:c.jsx(di,{size:14})})]}),c.jsxs("div",{className:"twin-stage",ref:N,children:[c.jsx("div",{ref:F,style:{position:"absolute",inset:0}}),c.jsx("div",{ref:z,className:"twin-labels"}),D&&c.jsxs("div",{className:"twin-overlay twin-info",children:[c.jsxs("b",{children:[D.lines.length," line",D.lines.length===1?"":"s"," · ",(2*D.span).toFixed(0)," m span · ",D.ground_short]}),c.jsx("br",{}),c.jsx("b",{children:"Colours:"})," ",st==="diff"?`what the shield changes in ${h}, in percent (teal = lower, red = higher).`:`the ${h==="B"?"magnetic":"electric"} field ${st==="with"?"with the shield in place":gt?"as it is without the shield":"(no shield is switched on)"}.`," ","Ground map: ",h," at ",D.meas_height," m above ground along the span, strongest at mid-span where the conductors hang lowest.",p.section&&c.jsxs(c.Fragment,{children:[" Section: ",h," in the plane z = ",ut.toFixed(0)," m."]}),gt&&st!=="without"&&c.jsxs(c.Fragment,{children:[" Shield acts over z = ",(D.shield.zc-D.shield.zh).toFixed(0),"…",(D.shield.zc+D.shield.zh).toFixed(0)," m."]})]}),D&&c.jsxs("div",{className:"twin-overlay twin-legend",children:[st==="diff"?c.jsx(Le,{diff:!0,dark:e==="dark",lo:"−70% lower",hi:"+70% higher",label:`Change in ${h} from the shield`}):c.jsx(Le,{lo:_==="log"?yt($t.max/1e3):"0",hi:yt($t.max),unit:ce,label:`${h==="B"?"Magnetic flux density":"Electric field"} (RMS)`}),st!=="diff"&&_!=="log"&&c.jsxs("div",{className:"colorbar mt-4",title:"Values above the top of the scale, mostly close to the conductors",children:[c.jsx("div",{className:"legend-bar",style:{background:ks(ns),height:6}}),c.jsxs("div",{className:"ends",children:[c.jsx("span",{children:"above scale ×1"}),c.jsx("span",{children:"×100"})]})]}),st!=="diff"&&c.jsx("div",{className:"tiny muted mt-4",children:$t.basis==="limit"?`Top of scale = limit. Peak is ${q?(100*bt/q).toFixed(bt/(q||1)<.1?1:0):"—"}% of it.`:$t.basis==="log"?"Logarithmic, three decades.":`Top of scale = ground-level peak${q?` (${(100*bt/q).toFixed(bt/q<.1?1:0)}% of the limit)`:""}.`}),c.jsx("button",{type:"button",className:"lg-toggle",onClick:()=>T(m=>!m),children:H?"Hide the key":"Show the key"}),H&&c.jsxs(c.Fragment,{children:[p.contours&&st!=="diff"&&c.jsxs(c.Fragment,{children:[q?c.jsxs("div",{className:"lg-row",children:[c.jsx("span",{className:"lg-line",style:{borderColor:"var(--red)"}}),"Limit ",yt(q)," ",ce,bt<q?" (not reached at ground)":""]}):null,c.jsxs("div",{className:"lg-row",children:[c.jsx("span",{className:"lg-line",style:{borderColor:"var(--violet)"}}),"Iso level ",yt(le)," ",ce]})]}),p.lines&&c.jsxs("div",{className:"lg-row",children:[["A","B","C"].map(m=>c.jsxs("span",{className:"row gap-4",children:[c.jsx("span",{className:"lg-line",style:{borderColor:`var(--phase-${m.toLowerCase()})`}}),m]},m)),c.jsx("span",{children:"phases"})]}),gt&&p.shield&&c.jsxs("div",{className:"lg-row",children:[c.jsx("span",{className:"lg-box",style:{background:"color-mix(in srgb, var(--teal) 45%, transparent)",border:"1px solid var(--teal-bright)"}}),"Shield",D.shield.mesh?" (mesh)":""]}),p.row&&c.jsxs("div",{className:"lg-row",children:[c.jsx("span",{className:"lg-box",style:{background:"var(--blue-tint)",border:"1px dashed var(--blue)"}}),"Right-of-way ±",D.row," m"]}),c.jsxs("div",{className:"lg-row",children:[c.jsx("span",{className:"swatch",style:{background:"var(--violet)"}}),"Pinned point · ",c.jsx("span",{className:"swatch",style:{background:"var(--blue-bright)"}})," receptor"]})]})]}),c.jsx("div",{className:"twin-overlay twin-hint",children:"Drag to orbit · scroll to zoom · right-drag to pan · click the ground, the section or a building to pin a point"}),c.jsx("div",{ref:U,className:"twin-overlay twin-tip"}),!D&&c.jsxs("div",{className:"twin-load",children:[c.jsx(Ls,{}),dt.error??"Building the site…"]}),D&&(dt.loading||p.section&&At.loading||(p.glow||p.iso)&&vt.loading&&!vt.data)&&c.jsx("div",{className:"busy-bar"})]}),c.jsxs("div",{className:"twin-foot",children:[c.jsxs("div",{className:"ctl",title:"Position of the field section along the line (0 = mid-span)",children:[c.jsx("span",{className:"lbl",children:"Section z"}),c.jsx("input",{type:"range",min:-kt,max:kt,step:Math.max(1,Math.round(kt/40)),value:ut,disabled:!p.section,onChange:m=>S(parseFloat(m.target.value)),"aria-label":"Section position"}),c.jsxs("b",{children:[ut>0?"+":ut<0?"−":"",Math.abs(ut).toFixed(0)," m"]}),c.jsx(ht,{size:"sm",variant:"ghost",onClick:()=>S(0),disabled:!p.section,children:"Mid-span"}),D&&D.buildings.length>0&&c.jsx(ht,{size:"sm",variant:"ghost",disabled:!p.section,onClick:()=>S(Math.max(-kt,Math.min(kt,D.buildings[0].z))),children:"At building"})]}),c.jsxs("div",{className:"row",title:"Level drawn as the violet contour and as the 3-D iso-surface",children:[c.jsx("span",{className:"lbl",children:"Iso level"}),c.jsx("div",{style:{width:104},children:h==="B"?c.jsx(Be,{value:n.twin.iso_level_uT,min:.01,max:5e3,step:.1,unit:"µT",onChange:m=>s(j=>{j.twin.iso_level_uT=m},{history:!1})}):c.jsx(Be,{value:M,min:.001,max:500,step:.1,unit:"kV/m",onChange:v})}),q?c.jsx(ht,{size:"sm",variant:"ghost",onClick:()=>h==="B"?s(m=>{m.twin.iso_level_uT=q},{history:!1}):v(q),children:"= limit"}):null]}),p.glow&&c.jsxs("div",{className:"row",style:{minWidth:190},children:[c.jsx("span",{className:"lbl",children:"Glow"}),c.jsx("input",{type:"range",min:0,max:1,step:.05,value:f,onChange:m=>y(parseFloat(m.target.value)),"aria-label":"Glow strength"})]}),c.jsxs(ht,{size:"sm",variant:"ghost",onClick:()=>B(m=>!m),children:[c.jsx(Bs,{size:13}),Lt.length," point",Lt.length===1?"":"s",A?c.jsx(Ue,{size:13}):c.jsx(ci,{size:13})]}),Lt.length>0&&c.jsxs(ht,{size:"sm",variant:"ghost",onClick:()=>i([]),title:"Remove every pinned point",children:[c.jsx(Fs,{size:13}),"Clear"]})]}),A&&Lt.length>0&&c.jsx("div",{className:"twin-pins",children:c.jsx(Os,{rows:Lt,onRemove:m=>i(n.points.filter((j,X)=>X!==m)),onLabel:(m,j)=>i(n.points.map((X,K)=>K===m?{...X,label:j}:X))})}),(t==null?void 0:t.shield.no_geometry)&&c.jsx("div",{className:"note",style:{borderRadius:0},children:"The shield is switched on but this configuration needs a building to attach to, so nothing is drawn."})]})})}export{nn as default};
