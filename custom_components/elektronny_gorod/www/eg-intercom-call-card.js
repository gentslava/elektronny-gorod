/* eg-intercom-call-card — собранный бандл. Источник: frontend/src/. Не редактировать вручную. */
var Ie=Object.defineProperty;var We=Object.getOwnPropertyDescriptor;var d=(s,t,e,i)=>{for(var r=i>1?void 0:i?We(t,e):t,n=s.length-1,o;n>=0;n--)(o=s[n])&&(r=(i?o(t,e,r):o(r))||r);return i&&r&&Ie(t,e,r),r};var Y=globalThis,G=Y.ShadowRoot&&(Y.ShadyCSS===void 0||Y.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,se=Symbol(),ve=new WeakMap,D=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==se)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(G&&t===void 0){let i=e!==void 0&&e.length===1;i&&(t=ve.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&ve.set(e,t))}return t}toString(){return this.cssText}},_e=s=>new D(typeof s=="string"?s:s+"",void 0,se),b=(s,...t)=>{let e=s.length===1?s[0]:t.reduce((i,r,n)=>i+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+s[n+1],s[0]);return new D(e,s,se)},be=(s,t)=>{if(G)s.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let i=document.createElement("style"),r=Y.litNonce;r!==void 0&&i.setAttribute("nonce",r),i.textContent=e.cssText,s.appendChild(i)}},ne=G?s=>s:s=>s instanceof CSSStyleSheet?(t=>{let e="";for(let i of t.cssRules)e+=i.cssText;return _e(e)})(s):s;var{is:Ke,defineProperty:Fe,getOwnPropertyDescriptor:Ye,getOwnPropertyNames:Ge,getOwnPropertySymbols:Xe,getPrototypeOf:Ze}=Object,X=globalThis,xe=X.trustedTypes,Je=xe?xe.emptyScript:"",Qe=X.reactiveElementPolyfillSupport,L=(s,t)=>s,j={toAttribute(s,t){switch(t){case Boolean:s=s?Je:null;break;case Object:case Array:s=s==null?s:JSON.stringify(s)}return s},fromAttribute(s,t){let e=s;switch(t){case Boolean:e=s!==null;break;case Number:e=s===null?null:Number(s);break;case Object:case Array:try{e=JSON.parse(s)}catch{e=null}}return e}},Z=(s,t)=>!Ke(s,t),ye={attribute:!0,type:String,converter:j,reflect:!1,useDefault:!1,hasChanged:Z};Symbol.metadata??=Symbol("metadata"),X.litPropertyMetadata??=new WeakMap;var k=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=ye){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let i=Symbol(),r=this.getPropertyDescriptor(t,i,e);r!==void 0&&Fe(this.prototype,t,r)}}static getPropertyDescriptor(t,e,i){let{get:r,set:n}=Ye(this.prototype,t)??{get(){return this[e]},set(o){this[e]=o}};return{get:r,set(o){let p=r?.call(this);n?.call(this,o),this.requestUpdate(t,p,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??ye}static _$Ei(){if(this.hasOwnProperty(L("elementProperties")))return;let t=Ze(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(L("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(L("properties"))){let e=this.properties,i=[...Ge(e),...Xe(e)];for(let r of i)this.createProperty(r,e[r])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[i,r]of e)this.elementProperties.set(i,r)}this._$Eh=new Map;for(let[e,i]of this.elementProperties){let r=this._$Eu(e,i);r!==void 0&&this._$Eh.set(r,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let i=new Set(t.flat(1/0).reverse());for(let r of i)e.unshift(ne(r))}else t!==void 0&&e.push(ne(t));return e}static _$Eu(t,e){let i=e.attribute;return i===!1?void 0:typeof i=="string"?i:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return be(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){let i=this.constructor.elementProperties.get(t),r=this.constructor._$Eu(t,i);if(r!==void 0&&i.reflect===!0){let n=(i.converter?.toAttribute!==void 0?i.converter:j).toAttribute(e,i.type);this._$Em=t,n==null?this.removeAttribute(r):this.setAttribute(r,n),this._$Em=null}}_$AK(t,e){let i=this.constructor,r=i._$Eh.get(t);if(r!==void 0&&this._$Em!==r){let n=i.getPropertyOptions(r),o=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:j;this._$Em=r;let p=o.fromAttribute(e,n.type);this[r]=p??this._$Ej?.get(r)??p,this._$Em=null}}requestUpdate(t,e,i,r=!1,n){if(t!==void 0){let o=this.constructor;if(r===!1&&(n=this[t]),i??=o.getPropertyOptions(t),!((i.hasChanged??Z)(n,e)||i.useDefault&&i.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,i))))return;this.C(t,e,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:r,wrapped:n},o){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),n!==!0||o!==void 0)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),r===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[r,n]of this._$Ep)this[r]=n;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[r,n]of i){let{wrapped:o}=n,p=this[r];o!==!0||this._$AL.has(r)||p===void 0||this.C(r,void 0,n,p)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(e)):this._$EM()}catch(i){throw t=!1,this._$EM(),i}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};k.elementStyles=[],k.shadowRootOptions={mode:"open"},k[L("elementProperties")]=new Map,k[L("finalized")]=new Map,Qe?.({ReactiveElement:k}),(X.reactiveElementVersions??=[]).push("2.1.2");var he=globalThis,we=s=>s,J=he.trustedTypes,$e=J?J.createPolicy("lit-html",{createHTML:s=>s}):void 0,Te="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,Ee="?"+P,et=`<${Ee}>`,C=document,q=()=>C.createComment(""),V=s=>s===null||typeof s!="object"&&typeof s!="function",ue=Array.isArray,tt=s=>ue(s)||typeof s?.[Symbol.iterator]=="function",oe=`[ 	
\f\r]`,B=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Ae=/-->/g,ke=/>/g,T=RegExp(`>|${oe}(?:([^\\s"'>=/]+)(${oe}*=${oe}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Se=/'/g,Me=/"/g,Ce=/^(?:script|style|textarea|title)$/i,ge=s=>(t,...e)=>({_$litType$:s,strings:t,values:e}),a=ge(1),St=ge(2),Mt=ge(3),S=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),Pe=new WeakMap,E=C.createTreeWalker(C,129);function Re(s,t){if(!ue(s)||!s.hasOwnProperty("raw"))throw Error("invalid template strings array");return $e!==void 0?$e.createHTML(t):t}var it=(s,t)=>{let e=s.length-1,i=[],r,n=t===2?"<svg>":t===3?"<math>":"",o=B;for(let p=0;p<e;p++){let l=s[p],g,m,h=-1,y=0;for(;y<l.length&&(o.lastIndex=y,m=o.exec(l),m!==null);)y=o.lastIndex,o===B?m[1]==="!--"?o=Ae:m[1]!==void 0?o=ke:m[2]!==void 0?(Ce.test(m[2])&&(r=RegExp("</"+m[2],"g")),o=T):m[3]!==void 0&&(o=T):o===T?m[0]===">"?(o=r??B,h=-1):m[1]===void 0?h=-2:(h=o.lastIndex-m[2].length,g=m[1],o=m[3]===void 0?T:m[3]==='"'?Me:Se):o===Me||o===Se?o=T:o===Ae||o===ke?o=B:(o=T,r=void 0);let w=o===T&&s[p+1].startsWith("/>")?" ":"";n+=o===B?l+et:h>=0?(i.push(g),l.slice(0,h)+Te+l.slice(h)+P+w):l+P+(h===-2?p:w)}return[Re(s,n+(s[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),i]},I=class s{constructor({strings:t,_$litType$:e},i){let r;this.parts=[];let n=0,o=0,p=t.length-1,l=this.parts,[g,m]=it(t,e);if(this.el=s.createElement(g,i),E.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(r=E.nextNode())!==null&&l.length<p;){if(r.nodeType===1){if(r.hasAttributes())for(let h of r.getAttributeNames())if(h.endsWith(Te)){let y=m[o++],w=r.getAttribute(h).split(P),F=/([.?@])?(.*)/.exec(y);l.push({type:1,index:n,name:F[2],strings:w,ctor:F[1]==="."?ce:F[1]==="?"?le:F[1]==="@"?de:O}),r.removeAttribute(h)}else h.startsWith(P)&&(l.push({type:6,index:n}),r.removeAttribute(h));if(Ce.test(r.tagName)){let h=r.textContent.split(P),y=h.length-1;if(y>0){r.textContent=J?J.emptyScript:"";for(let w=0;w<y;w++)r.append(h[w],q()),E.nextNode(),l.push({type:2,index:++n});r.append(h[y],q())}}}else if(r.nodeType===8)if(r.data===Ee)l.push({type:2,index:n});else{let h=-1;for(;(h=r.data.indexOf(P,h+1))!==-1;)l.push({type:7,index:n}),h+=P.length-1}n++}}static createElement(t,e){let i=C.createElement("template");return i.innerHTML=t,i}};function H(s,t,e=s,i){if(t===S)return t;let r=i!==void 0?e._$Co?.[i]:e._$Cl,n=V(t)?void 0:t._$litDirective$;return r?.constructor!==n&&(r?._$AO?.(!1),n===void 0?r=void 0:(r=new n(s),r._$AT(s,e,i)),i!==void 0?(e._$Co??=[])[i]=r:e._$Cl=r),r!==void 0&&(t=H(s,r._$AS(s,t.values),r,i)),t}var ae=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:i}=this._$AD,r=(t?.creationScope??C).importNode(e,!0);E.currentNode=r;let n=E.nextNode(),o=0,p=0,l=i[0];for(;l!==void 0;){if(o===l.index){let g;l.type===2?g=new W(n,n.nextSibling,this,t):l.type===1?g=new l.ctor(n,l.name,l.strings,this,t):l.type===6&&(g=new pe(n,this,t)),this._$AV.push(g),l=i[++p]}o!==l?.index&&(n=E.nextNode(),o++)}return E.currentNode=C,r}p(t){let e=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}},W=class s{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,r){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=H(this,t,e),V(t)?t===c||t==null||t===""?(this._$AH!==c&&this._$AR(),this._$AH=c):t!==this._$AH&&t!==S&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):tt(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==c&&V(this._$AH)?this._$AA.nextSibling.data=t:this.T(C.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:i}=t,r=typeof i=="number"?this._$AC(t):(i.el===void 0&&(i.el=I.createElement(Re(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(e);else{let n=new ae(r,this),o=n.u(this.options);n.p(e),this.T(o),this._$AH=n}}_$AC(t){let e=Pe.get(t.strings);return e===void 0&&Pe.set(t.strings,e=new I(t)),e}k(t){ue(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,i,r=0;for(let n of t)r===e.length?e.push(i=new s(this.O(q()),this.O(q()),this,this.options)):i=e[r],i._$AI(n),r++;r<e.length&&(this._$AR(i&&i._$AB.nextSibling,r),e.length=r)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let i=we(t).nextSibling;we(t).remove(),t=i}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},O=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,r,n){this.type=1,this._$AH=c,this._$AN=void 0,this.element=t,this.name=e,this._$AM=r,this.options=n,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=c}_$AI(t,e=this,i,r){let n=this.strings,o=!1;if(n===void 0)t=H(this,t,e,0),o=!V(t)||t!==this._$AH&&t!==S,o&&(this._$AH=t);else{let p=t,l,g;for(t=n[0],l=0;l<n.length-1;l++)g=H(this,p[i+l],e,l),g===S&&(g=this._$AH[l]),o||=!V(g)||g!==this._$AH[l],g===c?t=c:t!==c&&(t+=(g??"")+n[l+1]),this._$AH[l]=g}o&&!r&&this.j(t)}j(t){t===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},ce=class extends O{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===c?void 0:t}},le=class extends O{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==c)}},de=class extends O{constructor(t,e,i,r,n){super(t,e,i,r,n),this.type=5}_$AI(t,e=this){if((t=H(this,t,e,0)??c)===S)return;let i=this._$AH,r=t===c&&i!==c||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,n=t!==c&&(i===c||r);r&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},pe=class{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){H(this,t)}};var rt=he.litHtmlPolyfillSupport;rt?.(I,W),(he.litHtmlVersions??=[]).push("3.3.3");var He=(s,t,e)=>{let i=e?.renderBefore??t,r=i._$litPart$;if(r===void 0){let n=e?.renderBefore??null;i._$litPart$=r=new W(t.insertBefore(q(),n),n,void 0,e??{})}return r._$AI(s),r};var me=globalThis,_=class extends k{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=He(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};_._$litElement$=!0,_.finalized=!0,me.litElementHydrateSupport?.({LitElement:_});var st=me.litElementPolyfillSupport;st?.({LitElement:_});(me.litElementVersions??=[]).push("4.2.2");var A=s=>(t,e)=>{e!==void 0?e.addInitializer(()=>{customElements.define(s,t)}):customElements.define(s,t)};var nt={attribute:!0,type:String,converter:j,reflect:!1,hasChanged:Z},ot=(s=nt,t,e)=>{let{kind:i,metadata:r}=e,n=globalThis.litPropertyMetadata.get(r);if(n===void 0&&globalThis.litPropertyMetadata.set(r,n=new Map),i==="setter"&&((s=Object.create(s)).wrapped=!0),n.set(e.name,s),i==="accessor"){let{name:o}=e;return{set(p){let l=t.get.call(this);t.set.call(this,p),this.requestUpdate(o,l,s,!0,p)},init(p){return p!==void 0&&this.C(o,void 0,s,p),p}}}if(i==="setter"){let{name:o}=e;return function(p){let l=this[o];t.call(this,p),this.requestUpdate(o,l,s,!0,p)}}throw Error("Unsupported decorator location: "+i)};function u(s){return(t,e)=>typeof e=="object"?ot(s,t,e):((i,r,n)=>{let o=r.hasOwnProperty(n);return r.constructor.createProperty(n,i),o?Object.getOwnPropertyDescriptor(r,n):void 0})(s,t,e)}function f(s){return u({...s,state:!0,attribute:!1})}var at=new Set(["idle","ringing","connecting","active","ended","error"]);function Oe(s){return s&&at.has(s)?s:"idle"}var U={visible:!1,video:"none",actions:[],showOpen:!1,showTimer:!1,showAnswerWindow:!1,busy:!1,isError:!1};function Ue(s){switch(s){case"ringing":return{...U,visible:!0,video:"doorbell",actions:["reject","accept"],showOpen:!0,showAnswerWindow:!0};case"connecting":return{...U,visible:!0,video:"doorbell",actions:["cancel","connecting"],showOpen:!0,busy:!0};case"active":return{...U,visible:!0,video:"call",actions:["mic","sound","hangup"],showOpen:!0,showTimer:!0};case"error":return{...U,visible:!0,video:"none",actions:["retry","hangup"],showOpen:!0,isError:!0};case"ended":return{...U,visible:!0,video:"call",actions:["close"],showOpen:!0};case"idle":default:return{...U}}}var ze={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},te=s=>(...t)=>({_$litDirective$:s,values:t}),ee=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,i){this._$Ct=t,this._$AM=e,this._$Ci=i}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var R=class extends ee{constructor(t){if(super(t),this.it=c,t.type!==ze.CHILD)throw Error(this.constructor.directiveName+"() can only be used in child bindings")}render(t){if(t===c||t==null)return this._t=void 0,this.it=t;if(t===S)return t;if(typeof t!="string")throw Error(this.constructor.directiveName+"() called with a non-string value");if(t===this.it)return this._t;this.it=t;let e=[t];return e.raw=e,this._t={_$litType$:this.constructor.resultType,strings:e,values:[]}}};R.directiveName="unsafeHTML",R.resultType=1;var vi=te(R);var K=class extends R{};K.directiveName="unsafeSVG",K.resultType=2;var Ne=te(K);var ct={"key-round":'<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',lock:'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',"lock-open":'<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',phone:'<path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"/>',"phone-off":'<path d="M10.1 13.9a14 14 0 0 0 3.732 2.668 1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2 18 18 0 0 1-12.728-5.272"/><path d="M22 2 2 22"/><path d="M4.76 13.582A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 .244.473"/>',mic:'<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',"mic-off":'<path d="M12 19v3"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M16.95 16.95A7 7 0 0 1 5 12v-2"/><path d="M18.89 13.23A7 7 0 0 0 19 12v-2"/><path d="m2 2 20 20"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/>',"volume-2":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',"volume-x":'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/>',x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',timer:'<line x1="10" x2="14" y1="2" y2="2"/><line x1="12" x2="15" y1="14" y2="11"/><circle cx="12" cy="14" r="8"/>',"refresh-cw":'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',"door-open":'<path d="M11 20H2"/><path d="M11 4.562v16.157a1 1 0 0 0 1.242.97L19 20V5.562a2 2 0 0 0-1.515-1.94l-4-1A2 2 0 0 0 11 4.561z"/><path d="M11 4H8a2 2 0 0 0-2 2v14"/><path d="M14 12h.01"/><path d="M22 20h-3"/>',"video-off":'<path d="M10.66 6H14a2 2 0 0 1 2 2v2.5l5.248-3.062A.5.5 0 0 1 22 7.87v8.196"/><path d="M16 16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2"/><path d="m2 2 20 20"/>',"wifi-off":'<path d="M12 20h.01"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/><path d="M5 12.859a10 10 0 0 1 5.17-2.69"/><path d="M19 12.859a10 10 0 0 0-2.007-1.523"/><path d="M2 8.82a15 15 0 0 1 4.177-2.643"/><path d="M22 8.82a15 15 0 0 0-11.288-3.764"/><path d="m2 2 20 20"/>',"circle-check":'<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',"chevron-right":'<path d="m9 18 6-6-6-6"/>',"bell-ring":'<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M22 8c0-2.3-.8-4.3-2-6"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/>',"loader-circle":'<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',"door-closed":'<path d="M10 12h.01"/><path d="M18 20V6a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v14"/><path d="M2 20h20"/>'},z=class extends _{constructor(){super(...arguments);this.name=""}render(){let e=ct[this.name]??"";return a`<svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >${Ne(e)}</svg>`}};z.styles=b`
    :host {
      display: inline-flex;
      width: var(--eg-icon-size, 24px);
      height: var(--eg-icon-size, 24px);
      line-height: 0;
      flex: none;
    }
    svg {
      width: 100%;
      height: 100%;
      display: block;
    }
  `,d([u()],z.prototype,"name",2),z=d([A("eg-icon")],z);function De(s,t){if(s==="call")return t.camera;if(s==="doorbell")return t.doorbell_camera??t.camera}var M=class extends _{constructor(){super(...arguments);this.muted=!1;this._provider="pending"}connectedCallback(){super.connectedCallback(),this._resolveProvider()}async _resolveProvider(){if(customElements.get("ha-camera-stream")){this._provider="ha";return}try{await window.loadCardHelpers?.()}catch{}customElements.get("ha-camera-stream")?this._provider="ha":customElements.get("webrtc-camera")?this._provider="webrtc":this._provider="none"}updated(e){this._provider==="webrtc"&&this._syncWebrtc(e)}_syncWebrtc(e){let i=this.renderRoot.querySelector("#webrtc-host");if(!(!i||!this.entity||!this.hass))if(e.has("entity")||e.has("_provider")||e.has("muted")||!this._webrtcEl){i.replaceChildren();let r=document.createElement("webrtc-camera");r.setConfig({entity:this.entity,muted:this.muted}),r.hass=this.hass,i.appendChild(r),this._webrtcEl=r}else this._webrtcEl.hass=this.hass}render(){if(!this.entity||!this.hass)return this._frame("video-off","\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u0438\u0434\u0435\u043E");let e=this.hass.states[this.entity];if(!e)return this._frame("video-off","\u041A\u0430\u043C\u0435\u0440\u0430 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u0430");switch(this._provider){case"pending":return this._frame("video-off","\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0432\u0438\u0434\u0435\u043E\u2026");case"ha":return a`
          <ha-camera-stream
            .hass=${this.hass}
            .stateObj=${e}
            .muted=${this.muted}
          ></ha-camera-stream>
        `;case"webrtc":return a`<div id="webrtc-host"></div>`;default:return this._frame("video-off","\u0412\u0438\u0434\u0435\u043E\u043F\u043B\u0435\u0435\u0440 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D \u2014 \u043E\u0431\u043D\u043E\u0432\u0438\u0442\u0435 HA \u0438\u043B\u0438 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u0435 advanced-camera-card")}}_frame(e,i){return a`
      <div class="frame" role="img" aria-label=${i}>
        <eg-icon name=${e}></eg-icon>
        <span>${i}</span>
      </div>
      ${c}
    `}};M.styles=b`
    :host {
      display: block;
      width: 100%;
      height: 100%;
    }
    ha-camera-stream,
    #webrtc-host {
      display: block;
      width: 100%;
      height: 100%;
    }
    /* реальный плеер заполняет область (object-fit самого видео — по потоку) */
    .frame {
      width: 100%;
      height: 100%;
      background: var(--secondary-background-color);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: var(--secondary-text-color);
      text-align: center;
      padding: 8px;
      box-sizing: border-box;
    }
    .frame eg-icon {
      --eg-icon-size: 40px;
    }
    .frame span {
      font-size: 0.85rem;
    }
  `,d([u({attribute:!1})],M.prototype,"hass",2),d([u()],M.prototype,"entity",2),d([u({type:Boolean})],M.prototype,"muted",2),d([f()],M.prototype,"_provider",2),M=d([A("eg-call-video")],M);var N=b`
  :host {
    --eg-primary: var(--primary-color, #03a9f4);
    --eg-success: var(--success-color, #4caf50);
    --eg-error: var(--error-color, #ef5350);
    --eg-warning: var(--warning-color, #ffb300);
    --eg-text: var(--primary-text-color, #e8e8e8);
    --eg-text-2: var(--secondary-text-color, #a6a6a6);
    --eg-text-3: var(--disabled-text-color, #787878);
    --eg-elevated: var(--secondary-background-color, #2a2a2a);
    --eg-card: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --eg-divider: var(--divider-color, #2e2e2e);
    --eg-on-fill: var(--text-primary-color, #ffffff);
    --eg-scrim: rgba(0, 0, 0, 0.72);
    --eg-r-card: 16px;
    --eg-r-md: 12px;
    --eg-r-full: 999px;
    --eg-mono: "Roboto Mono", ui-monospace, monospace;
    /* Тинты бейджей/баннеров = роль-цвет @ ~18% (эквивалент alpha 2E/1A из макета). */
    --eg-primary-bg: color-mix(in srgb, var(--eg-primary) 18%, transparent);
    --eg-success-bg: color-mix(in srgb, var(--eg-success) 18%, transparent);
    --eg-error-bg: color-mix(in srgb, var(--eg-error) 18%, transparent);
    --eg-warning-bg: color-mix(in srgb, var(--eg-warning) 18%, transparent);
  }
`,lt={idle:"var(--eg-text-2)",ringing:"var(--eg-warning)",connecting:"var(--eg-primary)",active:"var(--eg-success)",ended:"var(--eg-text-2)",error:"var(--eg-error)"};function fe(s){return lt[s]??"var(--eg-text-2)"}function dt(s){switch(s){case"camera_off":return"placeholder-camera";case"connection_lost":return"placeholder-connection";case"ended":return"video-dimmed";default:return"video"}}var x=class extends _{constructor(){super(...arguments);this.muted=!1;this.live=!1;this.soundOff=!1;this.timestamp="";this.stageState="live";this.audioBlocked=!1;this._unmute=()=>{this.dispatchEvent(new CustomEvent("unmute",{bubbles:!0,composed:!0}))}}render(){let e=dt(this.stageState);return e==="placeholder-camera"?this._placeholder("video-off","muted","\u0412\u0438\u0434\u0435\u043E \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u043E","\u0410\u0443\u0434\u0438\u043E\u0432\u044B\u0437\u043E\u0432 \u043F\u0440\u043E\u0434\u043E\u043B\u0436\u0430\u0435\u0442\u0441\u044F"):e==="placeholder-connection"?this._placeholder("wifi-off","err","\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435 \u043F\u0440\u0435\u0440\u0432\u0430\u043D\u043E","\u041F\u0440\u043E\u0431\u0443\u0435\u043C \u0432\u043E\u0441\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C\u2026"):a`
      <eg-call-video .hass=${this.hass} .entity=${this.entity} .muted=${this.muted}></eg-call-video>
      ${e==="video-dimmed"?a`<div class="dim" aria-hidden="true"></div>`:c}
      <div class="top">
        ${this.live?a`<span class="live"><span class="live-dot" aria-hidden="true"></span>LIVE</span>`:c}
        ${this.soundOff?a`<span class="chip"><eg-icon name="volume-x"></eg-icon>Звук выкл.</span>`:c}
      </div>
      ${this.timestamp&&!this.audioBlocked?a`<span class="ts">${this.timestamp}</span>`:c}
      ${this.audioBlocked?a`
            <button class="tap" @click=${this._unmute} aria-label="Включить звук"></button>
            <span class="cta" aria-hidden="true">
              <eg-icon name="volume-x"></eg-icon>Нажмите, чтобы включить звук
            </span>
          `:c}
    `}_placeholder(e,i,r,n){return a`
      <div class="fallback ${i}" role="img" aria-label=${r}>
        <eg-icon name=${e}></eg-icon>
        <span class="fb-title">${r}</span>
        <span class="fb-sub">${n}</span>
      </div>
    `}};x.styles=[N,b`
      :host {
        position: absolute;
        inset: 0;
        display: block;
      }
      eg-call-video {
        position: absolute;
        inset: 0;
      }
      .dim {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
      }
      /* верхний ряд оверлеев: LIVE (слева) + чип звука (справа) */
      .top {
        position: absolute;
        top: 12px;
        left: 12px;
        right: 12px;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        pointer-events: none;
      }
      .live {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 9px;
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.04em;
      }
      .live-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #fff;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px;
        border-radius: var(--eg-r-full);
        background: rgba(0, 0, 0, 0.63);
        color: #fff;
        font-size: 11px;
      }
      .chip eg-icon {
        --eg-icon-size: 14px;
      }
      .ts {
        position: absolute;
        left: 12px;
        bottom: 12px;
        font-size: 10px;
        color: rgba(255, 255, 255, 0.69);
        font-variant-numeric: tabular-nums;
        pointer-events: none;
      }
      /* CTA «включить звук» + прозрачный tap-слой поверх всего видео */
      .tap {
        position: absolute;
        inset: 0;
        border: none;
        background: transparent;
        cursor: pointer;
        z-index: 2;
      }
      /* CTA — в НИЖНЕЙ части видео (не перекрывает лицо звонящего), UX §8/§13 */
      .cta {
        position: absolute;
        left: 50%;
        bottom: 16px;
        transform: translateX(-50%);
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 18px;
        border-radius: var(--eg-r-full);
        background: var(--eg-scrim);
        color: #fff;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
        z-index: 3;
        pointer-events: none;
      }
      .cta eg-icon {
        --eg-icon-size: 18px;
      }
      /* плейсхолдеры (камера недоступна / связь прервана) */
      .fallback {
        position: absolute;
        inset: 0;
        background: var(--eg-card);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-align: center;
        padding: 12px;
        box-sizing: border-box;
      }
      .fallback eg-icon {
        --eg-icon-size: 36px;
        color: var(--eg-text-3);
      }
      .fallback.err eg-icon {
        color: var(--eg-error);
      }
      .fb-title {
        font-size: 15px;
        color: var(--eg-text);
      }
      .fb-sub {
        font-size: 12px;
        color: var(--eg-text-2);
      }
    `],d([u({attribute:!1})],x.prototype,"hass",2),d([u()],x.prototype,"entity",2),d([u({type:Boolean})],x.prototype,"muted",2),d([u({type:Boolean})],x.prototype,"live",2),d([u({type:Boolean})],x.prototype,"soundOff",2),d([u()],x.prototype,"timestamp",2),d([u()],x.prototype,"stageState",2),d([u({type:Boolean})],x.prototype,"audioBlocked",2),x=d([A("eg-call-stage")],x);function Le(s){return s<0?0:s>1?1:s}function pt(s,t,e,i){let r=Math.max(1,e-i);return Le((s-t-i/2)/r)}function ht(s,t){return Le(s/Math.max(1,t))}var ut=.92,gt=800,mt=68,$=class extends _{constructor(){super(...arguments);this.mode="hold";this.disabled=!1;this.label="\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C";this.status="idle";this._progress=0;this._arming=!1;this._raf=0;this._holdStart=0;this._trackRect=null;this._holdTick=()=>{if(this._progress=ht(performance.now()-this._holdStart,gt),this._progress>=1){this._reset(),this._fireOpen();return}this._raf=requestAnimationFrame(this._holdTick)};this._onHoldDown=e=>{this.disabled||(e.target.setPointerCapture?.(e.pointerId),this._arming=!0,this._holdStart=performance.now(),this._raf=requestAnimationFrame(this._holdTick))};this._onHoldUp=()=>{this._progress<1&&this._reset()};this._onSlideDown=e=>{if(this.disabled)return;let i=e.currentTarget.closest(".track");this._trackRect=i?.getBoundingClientRect()??null,e.target.setPointerCapture?.(e.pointerId),this._arming=!0};this._onSlideMove=e=>{!this._arming||!this._trackRect||(this._progress=pt(e.clientX,this._trackRect.left,this._trackRect.width,mt))};this._onSlideUp=()=>{this._progress>=ut?(this._reset(),this._fireOpen()):this._reset()};this._onTap=()=>{this.disabled||this._fireOpen()}}_fireOpen(){this.dispatchEvent(new CustomEvent("open",{bubbles:!0,composed:!0}))}_reset(){this._raf&&cancelAnimationFrame(this._raf),this._raf=0,this._arming=!1,this._progress=0,this._trackRect=null}render(){let e=this.mode==="tap"?this._renderTap():this.mode==="slide"?this._renderSlide():this._renderHold();return a`
      <div class="wrap" style="--eg-prog:${this._vp()}">
        ${e}
        ${this._caption()}
      </div>
    `}_caption(){let e="",i="";if(this.status==="opened")e="\u0414\u0432\u0435\u0440\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u0430",i="st-opened";else if(this.status==="error")e="\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u044C \xB7 \u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",i="st-error";else if(this.status==="opening")e="\u041E\u0442\u043A\u0440\u044B\u0432\u0430\u044E\u2026";else if(this.mode==="slide")e="\u0421\u0434\u0432\u0438\u043D\u044C\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C";else return a``;return a`<span class="caption ${i}">${e}</span>`}_labelText(){return this.status==="opened"?"\u041E\u0442\u043A\u0440\u044B\u0442\u043E":this.mode==="slide"?"\u041E\u0442\u043A\u0440\u044B\u0442\u044C":"\u0423\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0439\u0442\u0435, \u0447\u0442\u043E\u0431\u044B \u043E\u0442\u043A\u0440\u044B\u0442\u044C"}_barIcon(){return this.status==="opened"?"lock-open":"key-round"}_knobIcon(){return"key-round"}_vp(){return this.status==="opened"?1:this._progress}_statusClass(){return this.status==="opened"?"st-opened":this.status==="error"?"st-error":""}_renderTap(){return a`
      <button class="pill tap ${this._statusClass()}" ?disabled=${this.disabled} @click=${this._onTap}
              aria-label=${this.label}>
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `}_renderHold(){return a`
      <button
        class="pill hold ${this._arming?"arming":""} ${this._statusClass()}"
        ?disabled=${this.disabled}
        aria-label="${this.label} — удерживайте"
        @pointerdown=${this._onHoldDown}
        @pointerup=${this._onHoldUp}
        @pointercancel=${this._onHoldUp}
        @pointerleave=${this._onHoldUp}
      >
        <div class="fill"></div>
        <span class="content"><eg-icon name=${this._barIcon()}></eg-icon>${this._labelText()}</span>
      </button>
    `}_renderSlide(){return a`
      <div
        class="track ${this._statusClass()} ${this._arming?"dragging":""}"
        role="slider"
        aria-label=${this.label}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(this._vp()*100)}
      >
        <eg-icon class="lock-under" name="lock"></eg-icon>
        <eg-icon class="end" name="lock-open"></eg-icon>
        <div class="fill"></div>
        <span class="label">${this._labelText()}</span>
        <div
          class="knob ${this.disabled?"off":""}"
          @pointerdown=${this._onSlideDown}
          @pointermove=${this._onSlideMove}
          @pointerup=${this._onSlideUp}
          @pointercancel=${this._onSlideUp}
        >
          <eg-icon name=${this._knobIcon()}></eg-icon>
        </div>
      </div>
    `}};$.styles=[N,b`
      :host {
        display: block;
      }
      .wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
        align-items: center;
        width: 100%;
      }
      /* ---- общая заливка-прогресс ---- */
      .fill {
        position: absolute;
        inset: 0 auto 0 0;
        width: calc(var(--eg-prog, 0) * 100%);
        background: var(--eg-primary);
        opacity: 0.15;
        transition: width 0.2s ease;
      }
      /* ---- slide: трек 300×80 (макет: фиксированный, центрирован — не на всю ширину) ---- */
      .track {
        position: relative;
        width: 300px;
        max-width: 100%;
        height: 80px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        touch-action: none;
        user-select: none;
      }
      /* в покое заливки нет (иначе «залипло»); появляется только при перетаскивании */
      .track .fill {
        width: 0;
      }
      /* при drag правый край заливки строго = центр ключа (не обгоняет) */
      .track.dragging .fill {
        width: calc(40px + var(--eg-prog, 0) * (100% - 80px));
        transition: none;
      }
      /* закрытый замок под ключом (проявляется при отъезде): иконка 20, центр под ключом */
      .lock-under {
        position: absolute;
        left: 30px;
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: 20px;
        color: var(--eg-text-3);
        z-index: 0;
      }
      /* торец: открытый замок (макет: иконка 20, центр 28px от правого края) */
      .end {
        position: absolute;
        right: 18px;
        top: 50%;
        transform: translateY(-50%);
        --eg-icon-size: 20px;
        color: var(--eg-text-3);
        z-index: 0;
      }
      .track .label {
        position: relative;
        z-index: 1;
        font-size: 17px;
        font-weight: 600;
        color: var(--eg-text);
      }
      .knob {
        position: absolute;
        top: 6px;
        left: calc(6px + var(--eg-prog, 0) * (100% - 80px));
        width: 68px;
        height: 68px;
        border-radius: 50%;
        background: var(--eg-primary);
        color: var(--eg-on-fill);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        touch-action: none;
        z-index: 2;
        --eg-icon-size: 28px;
        transition: left 0.18s ease;
      }
      .track.dragging .knob {
        transition: none;
        cursor: grabbing;
      }
      .knob.off {
        opacity: 0.5;
      }
      /* slide success: зелёный трек + «Открыто» + ключ справа */
      .track.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .track.st-opened .label {
        color: var(--eg-on-fill);
      }
      .track.st-opened .knob {
        background: var(--eg-success);
      }
      /* success: ключ-knob уехал вправо и накрыл торец — торец прячем */
      .track.st-opened .end {
        display: none;
      }
      /* ---- hold/tap: outlined-пилюля, контент неподвижен, заливка бежит ---- */
      .pill {
        position: relative;
        width: 100%;
        min-height: 64px;
        border-radius: var(--eg-r-full);
        border: 2px solid var(--eg-primary);
        background: transparent;
        color: var(--eg-text);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        cursor: pointer;
        touch-action: none;
        user-select: none;
        font: inherit;
        padding: 0 16px;
      }
      .pill.arming .fill {
        transition: none;
      }
      .pill .fill {
        opacity: 0.2;
      }
      .pill .content {
        position: relative;
        z-index: 1;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 17px;
        font-weight: 600;
        --eg-icon-size: 24px;
      }
      .pill[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .pill.st-opened {
        border-color: var(--eg-success);
      }
      .pill.st-opened .fill {
        background: var(--eg-success);
        opacity: 1;
        width: 100%;
      }
      .pill.st-opened .content {
        color: var(--eg-on-fill);
      }
      /* ---- подпись под контролом ---- */
      .caption {
        font-size: 12px;
        color: var(--eg-text-3);
        text-align: center;
      }
      .caption.st-opened {
        color: var(--eg-success);
      }
      .caption.st-error {
        color: var(--eg-error);
      }
      @media (prefers-reduced-motion: reduce) {
        .fill,
        .knob {
          transition: none;
        }
      }
    `],d([u()],$.prototype,"mode",2),d([u({type:Boolean})],$.prototype,"disabled",2),d([u()],$.prototype,"label",2),d([u()],$.prototype,"status",2),d([f()],$.prototype,"_progress",2),d([f()],$.prototype,"_arming",2),$=d([A("eg-open-control")],$);function je(s,t){return t&&s==="granted"}var ie=class{constructor(t,e=()=>{}){this._getConn=t;this._onChange=e;this.active=!1;this.lastError=""}async queryPermission(){try{return(await navigator.permissions?.query({name:"microphone"}))?.state??"unknown"}catch{return"unknown"}}get secure(){return typeof window<"u"&&window.isSecureContext===!0}async start(){if(this.active)return;let t=this._getConn();if(!t){this._fail("\u043D\u0435\u0442 \u0441\u0432\u044F\u0437\u0438 \u0441 Home Assistant");return}if(!navigator.mediaDevices?.getUserMedia){this._fail("\u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D (\u043D\u0443\u0436\u0435\u043D HTTPS-origin)");return}try{let e=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0}}),i=window.AudioContext||window.webkitAudioContext,r=new i,n=r.sampleRate,o=this._sub;(!o||o.sampleRate!==n)&&(o={handlerId:(await t.sendMessagePromise({type:"elektronny_gorod/intercom_uplink",sample_rate:n})).handler_id,sampleRate:n},this._sub=o);let p=o.handlerId,l=t.socket;await r.audioWorklet.addModule(this._workletUrl());let g=new AudioWorkletNode(r,"eg-pcm-int16",{numberOfOutputs:0});g.port.onmessage=h=>{let y=h.data,w=new Uint8Array(1+y.byteLength);w[0]=p,w.set(new Uint8Array(y.buffer),1),l.readyState===1&&l.send(w)};let m=r.createMediaStreamSource(e);m.connect(g),this._ctx={ac:r,stream:e,node:g,src:m},this.active=!0,this.lastError="",this._onChange()}catch(e){this._fail(e instanceof Error?e.message:String(e))}}stop(){let t=this._ctx;if(t){try{t.node.port.onmessage=null,t.node.disconnect(),t.src.disconnect()}catch{}try{t.stream.getTracks().forEach(e=>e.stop())}catch{}try{t.ac.close()}catch{}}if(this._ctx=void 0,this.active=!1,this._wUrl){try{URL.revokeObjectURL(this._wUrl)}catch{}this._wUrl=void 0}this._onChange()}_fail(t){this.lastError=t,this.stop()}_workletUrl(){if(this._wUrl)return this._wUrl;let t=`
      class EgPcmInt16 extends AudioWorkletProcessor {
        process(inputs) {
          const ch = inputs[0] && inputs[0][0];
          if (ch && ch.length) {
            const i16 = new Int16Array(ch.length);
            for (let i = 0; i < ch.length; i++) {
              const s = Math.max(-1, Math.min(1, ch[i]));
              i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
            }
            this.port.postMessage(i16, [i16.buffer]);
          }
          return true;
        }
      }
      registerProcessor("eg-pcm-int16", EgPcmInt16);`;return this._wUrl=URL.createObjectURL(new Blob([t],{type:"application/javascript"})),this._wUrl}};var ft=new Set(["slide","hold","tap"]);function Be(s,t){return s&&ft.has(s)?s:t?"slide":"hold"}function qe(){return typeof window<"u"&&typeof window.matchMedia=="function"&&window.matchMedia("(pointer: coarse)").matches}var vt={ringing:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432",connecting:"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026",active:"\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440",ended:"\u0412\u044B\u0437\u043E\u0432 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D",error:"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430"},re=new Set(["ringing","connecting","active","error"]),_t=6e3,bt=3e3,Ve=3e4,xt=2500,v=class extends _{constructor(){super(...arguments);this._config={};this._muted=!1;this._audioBlocked=!1;this._micActive=!1;this._micPerm="unknown";this._openStatus="idle";this._now=Date.now();this._ringingSince=0;this._errDismissed=new Set;this._endedEntity="";this._endedDuration="";this._doorbells=[];this._openAction="hold";this._prevKey="";this._prevPhases=new Map;this._mic=new ie(()=>this.hass?.connection,()=>{this._micActive=this._mic.active,this.requestUpdate()});this._clearEnded=()=>{this._endedHide&&(clearTimeout(this._endedHide),this._endedHide=void 0),this._endedEntity="",this.requestUpdate()};this._unmute=()=>{this._muted=!1,this._audioBlocked=!1};this._answer=()=>{this.hass?.callService("elektronny_gorod","answer")};this._hangup=()=>{this.hass?.callService("elektronny_gorod","hangup")};this._toggleMute=()=>{this._muted=!this._muted};this._toggleMic=async()=>{this._mic.active?this._mic.stop():await this._mic.start(),this._micPerm=await this._mic.queryPermission()};this._open=async()=>{let e=this._active?.lock;if(!(!e||!this.hass)){this._openStatus="opening";try{await this.hass.callService("lock","unlock",{entity_id:e}),this._openStatus="opened"}catch{this._openStatus="error"}this._openReset&&clearTimeout(this._openReset),this._openReset=window.setTimeout(()=>{this._openStatus="idle",this.requestUpdate()},bt)}};this._dismiss=()=>{this.dispatchEvent(new CustomEvent("eg-dismiss",{bubbles:!0,composed:!0}))};this._retry=()=>{this.hass?.callService("elektronny_gorod","answer")}}setConfig(e){let i=e?.doorbells??(e?.call_state?[{call_state:e.call_state,doorbell_camera:e.doorbell_camera,lock:e.lock,name:e.name,address:e.address}]:[]);if(!i.length||i.some(r=>!r.call_state))throw new Error("eg-intercom-call-card: \u0443\u043A\u0430\u0436\u0438\u0442\u0435 'doorbells' (\u0441 call_state) \u0438\u043B\u0438 'call_state'");this._config=e,this._doorbells=i,this._openAction=Be(e.open_action,qe())}getCardSize(){return 8}static getStubConfig(){return{camera:"",doorbells:[{call_state:"",doorbell_camera:"",lock:""}]}}disconnectedCallback(){super.disconnectedCallback(),this._mic.stop(),this._stopTick(),this._errHide&&clearTimeout(this._errHide),this._openReset&&clearTimeout(this._openReset),this._endedHide&&clearTimeout(this._endedHide)}_phaseOf(e){let i=this.hass?.states[e.call_state]?.state;return Oe(i)}get _active(){let e=this._doorbells.find(i=>re.has(this._phaseOf(i))&&!this._errDismissed.has(i.call_state));if(e)return e;if(this._endedEntity)return this._doorbells.find(i=>i.call_state===this._endedEntity)}get _phase(){let e=this._active;if(!e)return"idle";let i=this._phaseOf(e);return re.has(i)?i:e.call_state===this._endedEntity?"ended":"idle"}get _intercomName(){let e=this._active;if(e?.name)return e.name;let r=(e?this.hass?.states[e.call_state]?.attributes:void 0)?.intercom_name;return(typeof r=="string"?r.replace(/\s+/g," ").trim():"")||this._config.name||"\u0414\u043E\u043C\u043E\u0444\u043E\u043D"}get _address(){return this._active?.address??this._config.address??""}get _startedAtMs(){let e=this._active,i=e?this.hass?.states[e.call_state]?.attributes?.started_at:void 0;if(typeof i!="string")return;let r=Date.parse(i);return Number.isNaN(r)?void 0:r}willUpdate(e){if(!e.has("hass"))return;for(let n of this._doorbells){let o=this._phaseOf(n),p=this._prevPhases.get(n.call_state);this._prevPhases.set(n.call_state,o),this._errDismissed.has(n.call_state)&&o!=="error"&&this._errDismissed.delete(n.call_state),o==="ended"&&p!==void 0&&re.has(p)&&p!=="error"&&this._enterEnded(n),this._endedEntity===n.call_state&&re.has(o)&&this._clearEnded()}let i=this._active,r=i?`${i.call_state}|${this._phase}`:"idle";r!==this._prevKey&&(this._onPhase(this._phase,i),this._prevKey=r)}_enterEnded(e){this._endedDuration=this._durationOf(e),this._endedEntity=e.call_state,this._endedHide&&clearTimeout(this._endedHide),this._endedHide=window.setTimeout(()=>this._clearEnded(),xt)}_durationOf(e){let i=this.hass?.states[e.call_state]?.attributes?.started_at;if(typeof i!="string")return"";let r=Date.parse(i);return Number.isNaN(r)?"":this._mmss(Math.max(0,Math.floor((Date.now()-r)/1e3)))}_onPhase(e,i){e==="active"?this._enterActive():e==="ringing"?(this._ringingSince=Date.now(),this._startTick()):this._exitActive(),e==="error"&&i&&this._scheduleErrDismiss(i.call_state),(e==="idle"||e==="ringing")&&(this._openStatus="idle")}async _enterActive(){this._muted=!1,this._audioBlocked=this._detectAudioBlocked(),this._startTick(),this._micPerm=await this._mic.queryPermission(),this._config.mic_autostart!==!1&&je(this._micPerm,this._mic.secure)&&await this._mic.start()}_detectAudioBlocked(){let e=navigator.userActivation;return e?!e.hasBeenActive:!1}_exitActive(){this._mic.stop(),this._stopTick(),this._audioBlocked=!1}_startTick(){this._stopTick(),this._now=Date.now(),this._tick=window.setInterval(()=>{this._now=Date.now()},1e3)}_stopTick(){this._tick&&(clearInterval(this._tick),this._tick=void 0)}_scheduleErrDismiss(e){this._errHide&&clearTimeout(this._errHide),this._errHide=window.setTimeout(()=>{this._errDismissed=new Set(this._errDismissed).add(e),this.requestUpdate()},_t)}_timerText(){let e=this._startedAtMs;if(e===void 0)return"";let i=Math.max(0,Math.floor((this._now-e)/1e3));return this._mmss(i)}_mmss(e){let i=String(Math.floor(e/60)).padStart(2,"0"),r=String(e%60).padStart(2,"0");return`${i}:${r}`}_answerWindow(){if(!this._ringingSince)return{text:"",fraction:0};let e=Math.max(0,Ve-(this._now-this._ringingSince)),i=Math.ceil(e/1e3);return{text:`${Math.floor(i/60)}:${String(i%60).padStart(2,"0")}`,fraction:e/Ve}}_stageState(e,i,r){if(r==="ended")return"ended";if(e.isError)return"connection_lost";let n=i?this.hass?.states[i]:void 0;return!n||n.state==="unavailable"?"camera_off":"live"}get _micNeedsPermission(){return this._config.mic===!1||this._phase!=="active"||this._micActive?!1:!this._mic.secure||this._micPerm==="denied"||this._micPerm==="prompt"}get _micBlocked(){return!this._mic.secure||this._micPerm==="denied"}_timestamp(e){if(e!=="live")return"";let i=new Date(this._now),r=n=>String(n).padStart(2,"0");return`${r(i.getDate())}-${r(i.getMonth()+1)}-${i.getFullYear()} ${r(i.getHours())}:${r(i.getMinutes())}:${r(i.getSeconds())}`}render(){let e=this._active;if(!e)return this._renderIdle();let i=this._phase,r=Ue(i),n=De(r.video,{camera:this._config.camera,doorbell_camera:e.doorbell_camera});if(this._config.layout==="compact")return this._renderCompact(e,i,r,n);let o=this._stageState(r,n,i);return a`
      <ha-card class="phase-${i}">
        <div class="content">
          ${this._renderHeader()}
          ${this._renderStatus(r,i)}
          <div class="stage">
            <eg-call-stage
              .hass=${this.hass}
              .entity=${n}
              .muted=${this._muted}
              .live=${o==="live"}
              .soundOff=${i==="active"&&this._muted&&!this._audioBlocked}
              .timestamp=${this._timestamp(o)}
              .stageState=${o}
              .audioBlocked=${this._audioBlocked}
              @unmute=${this._unmute}
            ></eg-call-stage>
          </div>
          <div class="controls">
            ${this._micNeedsPermission?this._renderMicBanner():c}
            <div class="open-area">
              ${r.showOpen?this._renderOpen():c}
            </div>
            ${this._renderActions(r)}
          </div>
        </div>
      </ha-card>
    `}_renderHeader(){let e=this._address;return a`
      <header>
        <div class="hgroup">
          <span class="name" title=${this._intercomName}>${this._intercomName}</span>
          ${e?a`<span class="addr">${e}</span>`:c}
        </div>
        <button class="close" @click=${this._dismiss} aria-label="Свернуть">
          <eg-icon name="x"></eg-icon>
        </button>
      </header>
    `}_renderStatus(e,i){let r=e.showTimer&&this._config.timer!=="off",n=e.showAnswerWindow?this._answerWindow():null;return a`
      <div class="statusrow">
        <div class="strow">
          <span class="badge" style="--badge:${fe(i)}">
            <span class="dot" aria-hidden="true"></span>
            <span>${vt[i]??""}</span>
          </span>
          ${n?a`<span class="countdown"><eg-icon name="timer"></eg-icon>${n.text}</span>`:r?a`<span class="timer">${this._timerText()}</span>`:i==="ended"&&this._endedDuration?a`<span class="timer ended-dur">${this._endedDuration}</span>`:c}
        </div>
        ${n?a`<div class="window"><div class="fill" style="width:${n.fraction*100}%"></div></div>`:c}
      </div>
    `}_doorbellNames(){return this._doorbells.map(e=>{let i=this.hass?.states[e.call_state]?.attributes?.intercom_name;return e.name??(typeof i=="string"?i:"")}).filter(Boolean)}_renderIdle(){let e=this._doorbellNames();return a`
      <ha-card class="idle">
        <div class="idle-box" role="status">
          <div class="idle-ico"><eg-icon name="door-closed"></eg-icon></div>
          <div class="idle-title">${this._config.idle_text??"\u041D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u043E\u0433\u043E \u0432\u044B\u0437\u043E\u0432\u0430"}</div>
          <div class="idle-sub">Видео появится при звонке в домофон</div>
          ${e.length?a`<div class="idle-chips">
                ${e.map(i=>a`<span class="chip"><eg-icon name="door-open"></eg-icon>${i}</span>`)}
              </div>`:c}
        </div>
      </ha-card>
    `}_renderCompact(e,i,r,n){let o=this._stageState(r,n,i);return a`
      <ha-card class="compact phase-${i}">
        <div class="cx-thumb">
          ${n?a`<eg-call-video .hass=${this.hass} .entity=${n} .muted=${!0}></eg-call-video>`:c}
          ${o==="live"?a`<span class="cx-live">LIVE</span>`:c}
        </div>
        <div class="cx-info">
          <span class="cx-name" title=${this._intercomName}>${this._intercomName}</span>
          <span class="cx-status" style="--badge:${fe(i)}">
            <span class="cx-dot" aria-hidden="true"></span>
            <span>${this._compactStatus(i)}</span>
          </span>
        </div>
        <div class="cx-btns">
          ${r.showOpen&&e.lock?this._quickBtn("key-round","\u041E\u0442\u043A\u0440\u044B\u0442\u044C",this._open,"q-open"):c}
          ${r.actions.map(p=>this._quickAction(p))}
        </div>
      </ha-card>
    `}_quickAction(e){switch(e){case"accept":return this._quickBtn("phone","\u041F\u0440\u0438\u043D\u044F\u0442\u044C",this._answer,"q-accept");case"reject":case"cancel":case"hangup":return this._quickBtn("phone-off","\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C",this._hangup,"q-reject");case"close":return this._quickBtn("x","\u0417\u0430\u043A\u0440\u044B\u0442\u044C",this._clearEnded,"");default:return c}}_quickBtn(e,i,r,n){return a`
      <button class="q-btn ${n}" @click=${r} aria-label=${i}>
        <eg-icon name=${e}></eg-icon>
      </button>
    `}_compactStatus(e){return e==="ringing"?`\u0412\u044B\u0437\u043E\u0432 \xB7 ${this._answerWindow().text}`:e==="active"?`\u0420\u0430\u0437\u0433\u043E\u0432\u043E\u0440 \xB7 ${this._timerText()}`:e==="connecting"?"\u0421\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u2026":e==="ended"?this._endedDuration?`\u0417\u0430\u0432\u0435\u0440\u0448\u0451\u043D \xB7 ${this._endedDuration}`:"\u0417\u0430\u0432\u0435\u0440\u0448\u0451\u043D":e==="error"?"\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0437\u043E\u0432\u0430":""}_renderMicBanner(){return a`
      <div class="mic-banner" role="alert">
        <eg-icon name="mic-off"></eg-icon>
        <div class="mb-text">
          <span class="mb-title">Нет доступа к микрофону</span>
          <span class="mb-sub">Вас не слышно. Разрешите доступ в браузере.</span>
        </div>
        <button class="mb-btn" @click=${this._toggleMic}>Разрешить</button>
      </div>
    `}_renderOpen(){return a`
      <eg-open-control
        .mode=${this._openAction}
        .status=${this._openStatus}
        ?disabled=${!this._active?.lock}
        @open=${this._open}
      ></eg-open-control>
    `}_circle(e,i,r,n=""){return a`
      <button class="circle ${n}" @click=${r} aria-label=${i}>
        <span class="ic"><eg-icon name=${e}></eg-icon></span>
        <small>${i}</small>
      </button>
    `}_renderActions(e){return a`<div class="actions">${e.actions.map(i=>this._renderAction(i))}</div>`}_renderAction(e){switch(e){case"accept":return this._circle("phone","\u041F\u0440\u0438\u043D\u044F\u0442\u044C",this._answer,"accept");case"reject":return this._circle("phone-off","\u041E\u0442\u043A\u043B\u043E\u043D\u0438\u0442\u044C",this._hangup,"reject");case"cancel":return this._circle("phone-off","\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C",this._hangup,"reject");case"connecting":return this._spinnerBtn("\u0421\u043E\u0435\u0434\u0438\u043D\u044F\u0435\u043C\u2026");case"mic":return this._config.mic===!1?c:this._renderMic();case"sound":return this._audioBlocked?this._circle("volume-x","\u0417\u0432\u0443\u043A \u0432\u044B\u043A\u043B.",this._unmute,"warn"):this._circle(this._muted?"volume-x":"volume-2","\u0417\u0432\u0443\u043A",this._toggleMute);case"hangup":return this._circle("phone-off","\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C",this._hangup,"reject");case"retry":return this._circle("refresh-cw","\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C",this._retry,"retry");case"close":return this._circle("x","\u0417\u0430\u043A\u0440\u044B\u0442\u044C",this._clearEnded);default:return c}}_spinnerBtn(e){return a`
      <div class="circle spinner-btn" role="status" aria-label=${e} aria-busy="true">
        <span class="ic"><eg-icon class="spin" name="loader-circle"></eg-icon></span>
        <small>${e}</small>
      </div>
    `}_renderMic(){if(this._micBlocked)return this._circle("mic-off","\u041D\u0435\u0442 \u0434\u043E\u0441\u0442\u0443\u043F\u0430",this._toggleMic,"mic-blocked");let e=this._micActive?"mic":"mic-off",i=this._micActive?"\u0412\u044B\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D":"\u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D";return a`<button class="circle" @click=${this._toggleMic} aria-label=${i}>
      <span class="ic"><eg-icon name=${e}></eg-icon></span><small>Микрофон</small>
    </button>`}};v.styles=[N,b`
      :host {
        display: block;
        height: 100%;
        /* адаптив по собственной ширине карточки (телефон / планшет / десктоп / панель) */
        container-type: inline-size;
      }
      ha-card {
        height: 100%;
        box-sizing: border-box;
        background: var(--eg-card);
        border-radius: var(--eg-r-card);
      }
      .content {
        display: flex;
        flex-direction: column;
        gap: 20px;
        padding: 6px 16px 28px;
        box-sizing: border-box;
      }
      /* зона контролов (баннер + слайдер + кнопки) — колонка */
      .controls {
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      /* ---- широкий контейнер (настенная панель / десктоп): 2 колонки ---- */
      @container (min-width: 760px) {
        .content {
          display: grid;
          grid-template-columns: 1fr 340px;
          grid-template-areas:
            "header header"
            "status status"
            "stage controls";
          column-gap: 28px;
          row-gap: 20px;
          align-items: start;
          padding: 24px;
        }
        header {
          grid-area: header;
        }
        .statusrow {
          grid-area: status;
        }
        .stage {
          grid-area: stage;
          align-self: start;
        }
        /* колонка контролов = высоте видео: слайдер по центру, кнопки по нижней кромке */
        .controls {
          grid-area: controls;
          position: relative;
          align-self: stretch;
          display: block;
        }
        .controls .mic-banner {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
        }
        .controls .open-area {
          position: absolute;
          top: 50%;
          left: 0;
          right: 0;
          transform: translateY(-50%);
        }
        .controls .actions {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
        }
      }
      /* ---- шапка: имя + адрес + свернуть ---- */
      header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }
      .hgroup {
        display: flex;
        flex-direction: column;
        gap: 3px;
        min-width: 0;
      }
      .name {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.15;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .addr {
        font-size: 13px;
        color: var(--eg-text-2);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .close {
        flex: none;
        width: 44px;
        height: 44px;
        border: none;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        color: var(--eg-text-2);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
      }
      .close eg-icon {
        --eg-icon-size: 20px;
      }
      /* ---- статус-строка: бейдж + таймер/countdown + окно ответа ---- */
      .statusrow {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .strow {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 5px 12px;
        border-radius: var(--eg-r-full);
        font-size: 13px;
        font-weight: 600;
        color: var(--badge, var(--eg-text-2));
        background: color-mix(in srgb, var(--badge, var(--eg-text-2)) 18%, transparent);
      }
      .badge .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
      }
      .countdown {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 15px;
        color: var(--eg-text-2);
      }
      .countdown eg-icon {
        --eg-icon-size: 15px;
      }
      .timer {
        font-family: var(--eg-mono);
        font-size: 17px;
        font-weight: 600;
        color: var(--eg-text);
        font-variant-numeric: tabular-nums;
      }
      .timer.ended-dur {
        color: var(--eg-text-3);
        font-weight: 500;
      }
      .window {
        width: 100%;
        height: 4px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        overflow: hidden;
      }
      .window .fill {
        height: 100%;
        border-radius: var(--eg-r-full);
        background: var(--eg-warning);
        transition: width 1s linear;
      }
      /* ---- баннер «нет доступа к микрофону» ---- */
      .mic-banner {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        border-radius: var(--eg-r-md);
        background: var(--eg-warning-bg);
      }
      .mic-banner > eg-icon {
        --eg-icon-size: 20px;
        color: var(--eg-warning);
      }
      .mb-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        flex: 1;
        min-width: 0;
      }
      .mb-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--eg-warning);
      }
      .mb-sub {
        font-size: 12px;
        color: var(--eg-text-2);
      }
      .mb-btn {
        flex: none;
        border: 1px solid var(--eg-warning);
        background: transparent;
        color: var(--eg-warning);
        font: inherit;
        font-size: 13px;
        font-weight: 600;
        border-radius: var(--eg-r-full);
        padding: 6px 14px;
        cursor: pointer;
      }
      /* ---- видео-стейдж ---- */
      .stage {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        border-radius: var(--eg-r-md);
        overflow: hidden;
        background: var(--eg-elevated);
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .spin {
          animation: none;
        }
      }
      /* ---- зона «Открыть» ---- */
      .open-area {
        display: flex;
        justify-content: center;
      }
      .open-area eg-open-control {
        width: 100%;
      }
      /* ---- ряд действий: круги top-align (как в макете), gap 28 ---- */
      .actions {
        display: flex;
        gap: 28px;
        justify-content: center;
        align-items: flex-start;
        flex-wrap: wrap;
      }
      .circle {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        border: none;
        background: none;
        cursor: pointer;
        color: var(--eg-text);
        font: inherit;
        padding: 0;
      }
      .circle .ic {
        width: 68px;
        height: 68px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .circle .ic eg-icon {
        --eg-icon-size: 28px;
      }
      .circle small {
        font-size: 12px;
        font-weight: 500;
        color: var(--eg-text-2);
      }
      .circle[disabled] {
        cursor: not-allowed;
        opacity: 0.5;
      }
      /* Все кнопки ряда — единый стиль: круг 68, иконка 28, подпись fs12/fw500/text-2.
         Акцент действия — только ЦВЕТОМ круга (см. call-card-ux-production.md §6/§9). */
      .circle.accept .ic {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .circle.reject .ic {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
      .circle.retry .ic {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      /* audio_blocked: «Звук выкл.» — warning-иконка на elevated */
      .circle.warn .ic {
        color: var(--eg-warning);
      }
      .circle.warn small {
        color: var(--eg-warning);
      }
      /* микрофон недоступен: красный индикатор «Нет доступа» (iUNo1) */
      .circle.mic-blocked .ic {
        background: var(--eg-error-bg);
        color: var(--eg-error);
      }
      .circle.mic-blocked small {
        color: var(--eg-error);
      }
      /* «Соединяем…» — неинтерактивно, приглушённый крутящийся loader */
      .spinner-btn {
        cursor: default;
      }
      .spinner-btn small {
        color: var(--eg-text-3);
      }
      .spinner-btn .ic eg-icon.spin {
        color: var(--eg-text-2);
        animation: spin 0.9s linear infinite;
      }
      /* ---- idle-заглушка (узел aSs3Z) ---- */
      ha-card.idle {
        height: 100%;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 18px;
      }
      .idle-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 14px;
        text-align: center;
      }
      .idle-ico {
        width: 52px;
        height: 52px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .idle-ico eg-icon {
        --eg-icon-size: 24px;
        color: var(--eg-text-3);
      }
      .idle-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--eg-text);
      }
      .idle-sub {
        font-size: 12px;
        color: var(--eg-text-2);
        max-width: 34ch;
      }
      .idle-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: center;
        padding-top: 4px;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: var(--eg-r-full);
        background: var(--eg-elevated);
        color: var(--eg-text-2);
        font-size: 12px;
        font-weight: 500;
      }
      .chip eg-icon {
        --eg-icon-size: 14px;
        color: var(--eg-text-2);
      }
      /* ---- компактная строка (layout: compact) — узел aSs3Z ---- */
      ha-card.compact {
        height: auto;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        box-sizing: border-box;
      }
      .cx-thumb {
        position: relative;
        width: 80px;
        height: 60px;
        flex: none;
        border-radius: 10px;
        overflow: hidden;
        background: #20262b;
      }
      .cx-thumb eg-call-video {
        position: absolute;
        inset: 0;
      }
      .cx-live {
        position: absolute;
        top: 6px;
        left: 6px;
        padding: 2px 6px;
        border-radius: var(--eg-r-full);
        background: rgba(211, 47, 47, 0.88);
        color: #fff;
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 0.04em;
      }
      .cx-info {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .cx-name {
        font-size: 15px;
        font-weight: 700;
        color: var(--eg-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .cx-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 500;
        color: var(--badge, var(--eg-text-2));
      }
      .cx-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--badge, var(--eg-text-2));
        flex: none;
      }
      .cx-btns {
        display: flex;
        gap: 8px;
        flex: none;
      }
      .q-btn {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--eg-elevated);
        color: var(--eg-text);
      }
      .q-btn eg-icon {
        --eg-icon-size: 20px;
      }
      .q-btn.q-open {
        background: var(--eg-primary);
        color: var(--eg-on-fill);
      }
      .q-btn.q-accept {
        background: var(--eg-success);
        color: var(--eg-on-fill);
      }
      .q-btn.q-reject {
        background: var(--eg-error);
        color: var(--eg-on-fill);
      }
    `],d([u({attribute:!1})],v.prototype,"hass",2),d([f()],v.prototype,"_config",2),d([f()],v.prototype,"_muted",2),d([f()],v.prototype,"_audioBlocked",2),d([f()],v.prototype,"_micActive",2),d([f()],v.prototype,"_micPerm",2),d([f()],v.prototype,"_openStatus",2),d([f()],v.prototype,"_now",2),d([f()],v.prototype,"_ringingSince",2),d([f()],v.prototype,"_errDismissed",2),d([f()],v.prototype,"_endedEntity",2),d([f()],v.prototype,"_endedDuration",2),v=d([A("eg-intercom-call-card")],v);window.customCards=window.customCards||[];window.customCards.push({type:"eg-intercom-call-card",name:"\u042D\u0413 \u0414\u043E\u043C\u043E\u0444\u043E\u043D \u2014 \u042D\u043A\u0440\u0430\u043D \u0432\u044B\u0437\u043E\u0432\u0430",description:"\u0412\u0445\u043E\u0434\u044F\u0449\u0438\u0439 \u0432\u044B\u0437\u043E\u0432 \u0438 \u0440\u0430\u0437\u0433\u043E\u0432\u043E\u0440 \u0441 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u043E\u043C: \u0432\u0438\u0434\u0435\u043E+\u0437\u0432\u0443\u043A, \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u0434\u0432\u0435\u0440\u044C, \u043F\u0440\u0438\u043D\u044F\u0442\u044C/\u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044C, \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D. \u041E\u0434\u043D\u0430 \u043A\u0430\u0440\u0442\u0430 \u043D\u0430 \u0432\u0441\u0435 \u0434\u043E\u043C\u043E\u0444\u043E\u043D\u044B.",preview:!1});export{v as EgIntercomCallCard};
